"""
Invokes generator for config&init tlb when the module is run as a script.
Example: python3 tlb_gen.py
Additional flags:
    [-c, --config_path  ] - path to config file        (str, default="config.csv")
    [-t, --template_path] - path to asm template file  (str, default="asm_template.S")
    [-r, --asm_res_path ] - path to asm result file    (str, default="asm.S")
    [-p, --page_size    ] - tlb page size in KB**      (int, default=16384)
    [-w, --wired        ] - value of wired register    (int, default=8)
       ** [4KB, 16KB, 64KB, 256KB, 1MB, 4MB, 16MB]
"""

import math
import re
from functools import reduce
from optparse import OptionParser
from string import Template


class Entry:
    flags_mask = {
        'g': 0x1,  # global
        'v': 0x2,  # valid
        'd': 0x4,  # dirty
        'c': 0x0,  # cacheable
        'u': 0x38  # uncacheable
    }

    def __init__(self, start_phys_addr, start_virt_addr, flags):
        self.start_phys_addr = start_phys_addr
        self.start_virt_addr = start_virt_addr
        self.flags = list(map(str.lower, flags))
        if 'c' not in self.flags:  # if not cacheable -> add uncacheable flag to flags list
            self.flags.append('u')

        flags_val = reduce((lambda x, y: x | y), list(map(lambda e: Entry.flags_mask.get(e), self.flags)))
        self.entry_lo0 = flags_val | (start_phys_addr >> 6)
        self.entry_lo1 = self.entry_lo0 + 0x40000


def file_parse(file: list) -> list:
    entries = []
    read_indexes = [i for i, e in enumerate(file) if "___;" in e]
    file = file[read_indexes[1] + 1: read_indexes[2]]
    file = list(map(lambda e: re.sub(r"\(.*\)", "", e), file))
    file = list(map(lambda e: e.replace("_", ""), file))
    file = list(map(lambda e: " ".join(e.split()), file))

    for line in file:
        start_phys_addr = int(line.split(";")[0].strip(), 0)
        start_virt_addr = int(line.split(";")[1].strip(), 0)
        flags = (line.split(";")[3].strip()).split(" ")

        entries.append(Entry(start_phys_addr, start_virt_addr, flags))

    return entries


def main():
    parser = OptionParser()
    parser.add_option("-c", "--config_path", dest="config_path", default="config.csv")
    parser.add_option("-t", "--template_path", dest="template_path", default="asm_template.S")
    parser.add_option("-r", "--asm_res_path", dest="asm_res_path", default="asm.S")
    parser.add_option("-p", "--page_size", dest="page_size", type=int, default=16384)
    parser.add_option("-w", "--wired", dest="wired", type=int, default=8)

    (options, args) = parser.parse_args()
    tlb_page_size = int(options.page_size)
    wired = int(options.wired)
    wired = wired if 0 < wired < 16 else 8

    page_mask = {
        4: 0x0 << 13,
        16: 0x3 << 13,
        64: 0xf << 13,
        256: 0x3f << 13,
        1024: 0xff << 13,
        4096: 0x3ff << 13,
        16384: 0xfff << 13
    }.get(tlb_page_size)

    odd_bit = int(math.log2(page_mask + 0x1000))
    virt_addr_mask = ["1"] * (32 - odd_bit - 1)
    virt_addr_mask.extend(["0"] * (odd_bit + 1))
    virt_addr_mask = int("".join(virt_addr_mask), 2)

    with open(options.config_path) as config_file:
        config_file = config_file.readlines()

    entries = file_parse(config_file)  # type: [Entry]
    entries_count = len(entries)
    entries_count = entries_count if entries_count < 16 else 16
    macros_call = [
        "tlb_entry_init 0x{:08x} " \
        "0x{:08x} 0x{:08x} 0x{:08x}" \
        " 0x{:08x}".format(i, page_mask, entries[i].start_virt_addr, entries[i].entry_lo0, entries[i].entry_lo1) for i
        in range(entries_count)
        ]

    with open(options.template_path) as template_file:
        template_file = template_file.readlines()

    template = Template("".join(template_file))
    with open(options.asm_res_path, 'w') as res_file:
        res_file.write(
            template.substitute(
                tlb_page_size="0x{:08x}      ".format(page_mask),
                tlb_page_size_bytes=str(tlb_page_size),
                virt_addr_mask="0x{:08x}       ".format(virt_addr_mask),
                macros_call="\n    ".join(macros_call),
                wired=str(wired)
            )
        )


main()
