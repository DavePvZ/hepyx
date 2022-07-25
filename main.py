import os
from os import access
import sys  # sus
import curses
import typing

# -----------------------------------------------------
filename_pos: int = 1
# position of filename in argv (0~inf)
caps_hex: bool = True
# if true, 234 in hex will be 0xEA
# else if false, it will be 0xea
min_addr_num: int = 8
# minimum amount of nums in address
# std 8 - 32 bit offset which looks like "00000000",
# "00000010", "00000020", and etc
addr_hex_sep: str = "| "
# separator which stands between address and hex nums
maxy_minus: int = 1
# maxy_minus is number of rows, which must be minused
# to make correct output
spaces_hex: tuple = (0, 1, 0, 1, 0)
# 1 pos - after 2nd and 14th hex num
# 2 pos - after 4th and 12th hex num
# 3 pos - after 6th and 10th hex num
# 4 pos - after 8th hex num
# 5 pos - in other cases
hex_sym_sep: str = " | "
# separator between hex nums and symbols
syms_sep: str = ""
# separator between symbols
# -----------------------------------------------------


def main(sys_argv: list[str]) -> None:
    try:
        fname: str = sys_argv[filename_pos]
    except IndexError:
        raise ValueError("not enough arguments.") from None
    perms: tuple[bool, ...] = tuple([access(fname, perm) for perm in (os.F_OK,    # existance
                                                                      os.R_OK,    # readable
                                                                      os.W_OK,    # writeable
                                                                      os.X_OK)])  # executable
    # tbh all perms except writeable and executable can be removed
    # bc anyway if below won't let you further
    if not perms[1]:
        raise PermissionError(f"\"{fname}\" can't be {'read' if perms[0] else 'opened'}.")
    file: typing.BinaryIO = open(fname, mode=f"{'a' if perms[1] and perms[2] else 'r'}+b")
    stdscr = curses.initscr()
    curses.start_color()
    curses.set_tabsize(4)  # this can be removed bc anyway the's won't be any tabs
    curses.curs_set(0)
    curses.noecho()
    curses.raw()
    stdscr.keypad(True)
    # y - vertical
    # x - horizontal
    maxy, maxx = stdscr.getmaxyx()
    # dumb python can't understand that {lttr if perm else '-' for lttr, perm in zip(list('FRWX'), perms)}
    # is not a generator, so hehe ''.join() go brrrrrrrrrrrr
    perms_str: str = f"[{''.join(lttr if perm else '-' for lttr, perm in zip(list('FRWX'), perms))}]"
    # [vertical, horizontal]
    cursor: list[int, int] = [0, 0]
    file_offset: int = 0  # must be file_offset % 16 == 0
    # and yeah, this is also an up left corner
    file_size: int = get_size(file)
    size_len: int = len(hex(file_size)) - 2
    curr_encoding: str = "ascii"
    while True:
        stdscr.attron(curses.A_REVERSE)
        stdscr.addstr(0, 0, " " * maxx)
        stdscr.addstr(0, 0, f"  {perms_str}")
        stdscr.addstr(0, int((maxx-len(fname)) / 2), f"[{fname}]")
        stdscr.attroff(curses.A_REVERSE)

        # this must be optimized
        max_len: int = min_addr_num
        hex_start: str = ""
        for offset in range(file_offset, file_offset+(16*(maxy-1)), 16):
            rjusted_offset: str = (hex(offset))[2:].rjust(size_len, '0')
            max_len: int = len(rjusted_offset) if len(rjusted_offset) > max_len else max_len
        for line, offset in zip(range(1, maxy - 1), range(file_offset, file_offset+(16*(maxy-1)), 16)):
            # help
            rjusted_offset: str = (hex(offset))[2:].rjust(max_len, '0')
            stdscr.addstr(line, 0,
                          hex_start := (rjusted_offset + f"{addr_hex_sep}"))
        hex_start: int = len(hex_start)  # later this will be hor cords
        # NO, THIS CAN'T BE REFERENCED BEFORE ASSIGNMENT
        # BECAUSE I ASSIGNED IN PREVIOUS LINE YOU DUMB PYCHARM
        # (i fixed it)

        file.seek(file_offset, 0)
        spaces_between_hex: int = 0
        for line in range(1, maxy - maxy_minus):
            for block in range(16):
                curr_byte: bytes = file.read(1)
                hexed_byte: str = curr_byte.hex()
                hexed_byte: str = hexed_byte.upper() if caps_hex else hexed_byte
                for num, value in enumerate(((2, 16), (4, 12), (6, 10), (8, 3984))):
                    if block in value:
                        spaces_between_hex: int = spaces_hex[num]
                        break
                else:
                    spaces_between_hex: int = spaces_hex[4]
                stdscr.addstr(line,  # .                               Idk how to remove this without breaking an output
                              sum((hex_start, spaces_between_hex, (3*block), sum(int(block > i) for i in (4, 8, 12)))),
                              hexed_byte if len(curr_byte) else "..")
        syms_start: int = sum((hex_start, spaces_between_hex, 45, 3, 2))

        for line in range(1, maxy - maxy_minus):
            stdscr.addstr(line, syms_start, f"{hex_sym_sep}")
        syms_start += len(hex_sym_sep)
        file.seek(file_offset, 0)
        for line in range(1, maxy - maxy_minus):
            for block in range(16):
                curr_byte: str = file.read(1).decode(curr_encoding, "replace")
                # i found out that it replaces these symbols with 65533
                stdscr.addstr(line, sum((syms_start, block*(len(syms_sep)+1))),
                              curr_byte if curr_byte.isprintable() else ".")

        stdscr.attron(curses.A_REVERSE)
        # why this don't workkkkkkkkkkkkkkkk
        stdscr.addstr(maxy-1, 0, " " * (maxx-1))
        stdscr.attroff(curses.A_REVERSE)

        stdscr.refresh()
        stdscr.getch()
        break
    curses.endwin()
    file.close()


def get_size(fileobject: typing.IO) -> int:
    later = fileobject.tell()
    fileobject.seek(0, 2)
    actual_size = fileobject.tell()
    fileobject.seek(later, 0)
    return actual_size


if __name__ == "__main__":
    try:
        main(sys.argv)
    finally:
        curses.endwin()
