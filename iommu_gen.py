"""
Invokes generator for config&init iommu when the module is run as a script.
Example: python3 iommu_gen.py
Additional flags:
    [-c, --config_path ] - path to config file                               (str, default="config.csv")
    [-r, --cpp_res_path] - path to cpp result file                           (str, default="iommu_table.cpp")
    [-p, --page_size   ] - tlb page size from list [512GB, 1GB, 2MB, 4KB]    (str, default="2MB")
    [-u, --unmap_seg   ] - iommu base table address                          (int, default=0xcbff8000)
    [-b, --table_addr  ] - unmapped segment - start_address:end_address      (str, default="0:0")
    [    --pa_power    ] - power of physical address in bits                 (int, default=32)
    [    --iommu_power ] - power of physical address in iommu in bits        (int, default=40)
    [    --noelv_mode  ] - additional** to RISC-V iommu                      (True if active)
      **pa.ppn[i−1 : 0] = va.vpn[i−1 : 0] + pte.ppn[i−1 : 0]
"""
import re
from optparse import OptionParser


def get_bits(num, start, end):
    mask = ["1"] * (end - start + 1)
    mask.extend(["0"] * start)

    return (num & int("".join(mask), 2)) >> start


class IOMMUTable:
    A_PPN_BEG_BITS = [39, 30, 21, 12]  # 512GB, 1GB, 2MB, 4KB
    A_PPN_END_BITS = [47, 38, 29, 20]  # 512GB, 1GB, 2MB, 4KB
    OFFSET_BY_SIZE = [2 ** 39, 2 ** 30, 2 ** 21, 2 ** 12]  # 512GB, 1GB, 2MB, 4KB

    LEAF_LEVEL_BY_SIZE = {
        "512GB": 0,
        "1GB": 1,
        "2MB": 2,
        "4KB": 3
    }

    def __init__(self, base_adr, addr_map, page_size, unmapped_seg, pa_power, iommu_power, noelv_mode):
        leaf_level = IOMMUTable.LEAF_LEVEL_BY_SIZE.get(page_size)
        kb4 = self.OFFSET_BY_SIZE[self.LEAF_LEVEL_BY_SIZE.get("4KB")]

        # tlb page (entry in table) with 512 entries
        page_counter = [e for i, e in enumerate(self.A_PPN_BEG_BITS) if i <= leaf_level]
        page_counter = list(map(lambda e: pa_power - e if pa_power - e > 0 else 0, page_counter))
        self.entry_count = list(map(lambda e: 2 ** e, page_counter[:]))
        page_counter = map(lambda e: e - 9, page_counter)  # 2**e / 512
        page_counter = map(lambda e: e if e > 0 else 0, page_counter)
        page_counter = map(lambda e: 2 ** e, page_counter)
        lvls = list(page_counter)

        self.page_counter = sum(lvls)
        self.lvl_order = []
        self.pages = []

        lvls_bias = [sum(lvls[:i]) for i in range(len(lvls))]
        lvls_bias = list(map(lambda e: e * kb4, lvls_bias))

        # pointer pages
        pte_type = 1
        for lvl in range(leaf_level):
            for page in range(lvls[lvl]):
                self.lvl_order.append(lvl)
                adr = base_adr + lvls_bias[lvl + 1]
                entry_bias = 512 * page

                def cond(i): return self.entry_fill_cond(i, entry_bias, lvl)

                self.pages.append([self.make_pte(adr + i * kb4, pte_type) if cond(i) else 0 for i in range(512)])

        # leaf pages
        pte_type = 7
        for page in range(lvls[leaf_level]):
            self.lvl_order.append(leaf_level)
            offset = self.OFFSET_BY_SIZE[leaf_level]
            page_bias = page * 512 * offset

            def cond(i): return self.entry_fill_cond(i, 512 * page, leaf_level)

            self.pages.append([self.make_pte(i * offset + page_bias, pte_type) if cond(i) else 0 for i in range(512)])

        # config table changing in leaf pages
        pte_type = 7
        for va, pa in addr_map.items():
            lvl_bias = sum(lvls[:leaf_level])
            preleaf_lvl = leaf_level - 1 if leaf_level > 0 else 0
            page_bias = lvl_bias + get_bits(va, self.A_PPN_BEG_BITS[preleaf_lvl], self.A_PPN_END_BITS[preleaf_lvl])
            entry_bias = get_bits(va, self.A_PPN_BEG_BITS[leaf_level], self.A_PPN_END_BITS[leaf_level])

            adr = pa
            if not noelv_mode:
                adr = 2 ** iommu_power + pa - (get_bits(va, 12, 20) << 12)

            self.pages[page_bias][entry_bias] = self.make_pte(adr, pte_type)
            print("0x{:010x} -> 0x{:010x}".format(va, pa))

    @staticmethod
    def make_pte(adr, pte_type):
        valid = 1
        return adr >> 2 | pte_type << 1 | valid

    def entry_fill_cond(self, i, entry_bias, lvl):
        return i + entry_bias < self.entry_count[lvl]


def file_parse(file: list) -> dict:
    entries = {}
    read_indexs = [i for i, e in enumerate(file) if "___;" in e]
    file = file[read_indexs[4] + 1: read_indexs[5]]
    file = list(map(lambda e: re.sub(r"\(.*\)", "", e), file))
    file = list(map(lambda e: e.replace("_", ""), file))
    file = list(map(lambda e: " ".join(e.split()), file))

    for line in file:
        start_phys_addr = int(line.split(";")[0].strip(), 0)
        start_virt_addr = int(line.split(";")[1].strip(), 0)

        entries.update({start_virt_addr: start_phys_addr})

    return entries


def main():
    parser = OptionParser()
    parser.add_option("-c", "--config_path", dest="config_path", default="config.csv")
    parser.add_option("-r", "--cpp_res_path", dest="cpp_res_path", default="iommu_table.cpp")
    parser.add_option("-p", "--page_size", dest="page_size", default="2MB")
    parser.add_option("-u", "--unmap_seg", dest="unmap_seg", default="0:0")
    parser.add_option("-b", "--table_addr", dest="iommu_table_addr", type=int, default=0xcbff8000)
    parser.add_option("--pa_power", dest="pa_power", type=int, default=32)
    parser.add_option("--iommu_power", dest="iommu_power", type=int, default=40)
    parser.add_option("--noelv_mode", dest="noelv_mode", action="store_true")
    (options, args) = parser.parse_args()

    with open(options.config_path) as config_file:
        config_file = config_file.readlines()

    unmap_seg = options.unmap_seg.strip()
    unmap_seg = unmap_seg.split(":")
    unmap_seg = list(map(int, unmap_seg))

    addr_map = file_parse(config_file)
    iommu_table_addr = options.iommu_table_addr
    page_size = options.page_size.upper()
    pa_power = options.pa_power
    iommu_power = options.iommu_power
    noelv_mode = options.noelv_mode if options.noelv_mode else False
    iommu_table = IOMMUTable(iommu_table_addr, addr_map, page_size, unmap_seg, pa_power, iommu_power, noelv_mode)

    with open(options.cpp_res_path, 'w') as res_file:
        word_in_line = 32

        res_file.write(
            "// address of .iommu_table section is exactly " + str(hex(iommu_table_addr)) + "\n" +
            "unsigned long long int iommu_table[][" + str(iommu_table.page_counter) +
            "][512]  __attribute__ ((section (\".iommu_table\"))) = {\n" +
            " " * 2 + "// level 0 contains 1 meaningful entry (pointer to level1), " +
            "because VPN3 (VPN[47:39]) === 0 (virtual adr is 32 bits)\n" + " " * 2 + "{"
        )

        for ind, e in enumerate(iommu_table.pages):
            res_file.write("\n" + " " * 4 + "{ // level " + str(iommu_table.lvl_order[ind]))
            for i in range(word_in_line, len(e) + 1, word_in_line):
                res_file.write(
                    "\n" + " " * 6 +
                    ", ".join(list(map(lambda o: "0x{:010x}".format(o), e[i - word_in_line: i]))) + ", "
                )
            res_file.write("\n" + " " * 4 + "},")
        res_file.write("\n" + " " * 2 + "}\n};")


main()
