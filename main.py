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
spaces_hex: tuple = (1, 2, 1, 2, 1)
# 1 pos - after 2nd and 14th hex num
# 2 pos - after 4th and 12th hex num
# 3 pos - after 6th and 10th hex num
# 4 pos - after 8th hex num
# 5 pos - in other cases (1, 3, 5, 7, 9, 11, 13, 15)
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
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    # dumb python can't understand that {lttr if perm else '-' for lttr, perm in zip(list('FRWX'), perms)}
    # is not a generator, so hehe ''.join() go brrrrrrrrrrrr
    perms_str: str = f"[{''.join(lttr if perm else '-' for lttr, perm in zip(list('FRWX'), perms))}]"
    # [vertical, horizontal, field]
    # field:
    # 0 - hex field
    # 1 - symbols field
    cursor: list[int, int, int] = [0, 0, 0]
    file_offset: int = 0  # must be file_offset % 16 == 0
    # and yeah, this is also an up left corner
    file_size: int = os.path.getsize(fname)
    size_len: int = len(hex(file_size)) - 2
    curr_encoding: str = "ascii"
    while True:
        # this finally works :)
        stdscr.attron(curses.color_pair(1))
        stdscr.addstr(0, 0, " " * maxx)
        stdscr.addstr(maxy - maxy_minus, 0, " " * (maxx - 1))
        stdscr.addstr(0, 2, perms_str)
        stdscr.addstr(0, int((maxx-len(fname)) / 2), f"[{fname}]")
        stdscr.attroff(curses.color_pair(1))

        # this must be optimized
        max_len: int = min_addr_num
        hex_start: str = ''
        for offset in range(file_offset, file_offset+(16*(maxy-1)), 16):
            rjusted_offset: str = (hex(offset))[2:].rjust(size_len, '0')
            max_len: int = len(rjusted_offset) if len(rjusted_offset) > max_len else max_len
        for line, offset in zip(range(1, maxy - 1), range(file_offset, file_offset+(16*(maxy-1)), 16)):
            # help
            rjusted_offset: str = (hex(offset))[2:].rjust(max_len, '0')
            rjusted_offset = rjusted_offset.upper() if caps_hex else rjusted_offset
            stdscr.addstr(line, 0, hex_start := (rjusted_offset + f"{addr_hex_sep}"))
        hex_start: int = len(hex_start)  # later this will be hor cords
        # NO, THIS CAN'T BE REFERENCED BEFORE ASSIGNMENT
        # BECAUSE I ASSIGNED IN PREVIOUS LINE YOU DUMB PYCHARM
        # (i fixed it)

        file.seek(file_offset, 0)
        spaces_between_hex: int = 0
        for line in range(1, maxy - maxy_minus):
            stdscr.move(line, hex_start)
            for block in range(16):
                curr_byte: bytes = file.read(1)
                hexed_byte: str = curr_byte.hex()
                hexed_byte: str = hexed_byte.upper() if caps_hex else hexed_byte
                stdscr.addstr(hexed_byte if len(curr_byte) else "..",
                              curses.A_NORMAL if len(hexed_byte) else curses.A_DIM)
                stdscr.addstr(" " * spaces_hex[sum(counter if block in i
                                                   else 0 for counter, i in enumerate(((1, 13), (3, 11), (5, 9), (7,),
                                                                                       (0, 2, 4, 6, 8, 10, 12, 14))))])
        syms_start: int = sum((hex_start, spaces_between_hex, 45, 3, 2))

        for line in range(1, maxy - maxy_minus):
            stdscr.addstr(line, syms_start, f"{hex_sym_sep}")
        syms_start += len(hex_sym_sep)
        file.seek(file_offset, 0)
        for line in range(1, maxy - maxy_minus):
            for block in range(16):
                curr_byte: str = file.read(1).decode(curr_encoding, "replace")
                # i found out that it replaces these symbols with 65533
                curr_byte: str = curr_byte if curr_byte.isprintable() else "."
                stdscr.addstr(line, sum((syms_start, block*(len(syms_sep)+1))),
                              curr_byte if len(curr_byte) else ".", curses.A_NORMAL if len(curr_byte) else curses.A_DIM)

        hex_addr_symbol: str = hex(cursor[1])[2]
        stdscr.addstr(1+cursor[0], hex_start - len(hex_sym_sep),
                      hex_addr_symbol.upper() if caps_hex else hex_addr_symbol)
        file.seek(file_offset + (cursor[0] * 16) + cursor[1], 0)
        hexed_byte: bytes = file.read(1)
        if not cursor[2]:
            hexed_byte = hexed_byte.hex()
            hexed_byte = hexed_byte.upper() if caps_hex else hexed_byte
            stdscr.addstr(cursor[0]+1, sum((hex_start, cursor[1] * 2,
                                            sum(spaces_hex[sum(counter if block in i
                                                else 0 for counter, i in enumerate(((1, 13), (3, 11), (5, 9), (7,),
                                                                                    (0, 2, 4, 6, 8, 10, 12, 14))))]
                                                for block in range(0, cursor[1])))),
                          hexed_byte if len(hexed_byte) else "..", curses.color_pair(1))
        else:
            hexed_byte = hexed_byte.decode(curr_encoding, "replace")
            hexed_byte: str = hexed_byte if hexed_byte.isprintable() else "."
            stdscr.addstr(cursor[0]+1, sum((syms_start, cursor[1])),
                          hexed_byte if len(hexed_byte) else ".", curses.color_pair(1))

        stdscr.refresh()

        user_input = stdscr.getch()
        match user_input:
            case curses.KEY_DOWN:
                if cursor[0] < maxy - 3:
                    cursor[0] += 1
                else:
                    file_offset += 16
            case curses.KEY_UP:
                if cursor[0] > 0:
                    cursor[0] -= 1
                elif file_offset > 0:
                    file_offset -= 16
            case curses.KEY_RIGHT:
                if cursor[1] < 15:
                    cursor[1] += 1
                elif not cursor[2]:
                    cursor[2] = 1
                    cursor[1] = 0
            case curses.KEY_LEFT:
                if cursor[1] > 0:
                    cursor[1] -= 1
                elif cursor[2]:
                    cursor[2] = 0
                    cursor[1] = 15
            case 113:  # ord('q')
                break
    curses.endwin()
    file.close()


if __name__ == "__main__":
    try:
        main(sys.argv)
    finally:
        curses.endwin()
