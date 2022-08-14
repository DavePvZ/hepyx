import os
from os import access
import sys  # sus
import curses
import typing
import string
import logging

# -----------------------------------------------------
FILENAME_POS: int = 1
# position of filename in argv (0~inf)
HEX_CAPS: bool = True
# if true, 234 in hex will be 0xEA
# else if false, it will be 0xea
MIN_ADDR_NUM: int = 8
# minimum amount of nums in address
# std 8 - 32 bit offset which looks like "00000000",
# "00000010", "00000020", and etc
ADDR_HEX_SEP: str = "| "
# separator which stands between address and hex nums
SPACES_HEX: tuple = (1, 2, 1, 2, 1)
# 1 pos - after 2nd and 14th hex num
# 2 pos - after 4th and 12th hex num
# 3 pos - after 6th and 10th hex num
# 4 pos - after 8th hex num
# 5 pos - in other cases (1, 3, 5, 7, 9, 11, 13, 15)
HEX_SYM_SEP: str = " | "
# separator between hex nums and symbols
SYMS_SEP: str = ""
# separator between symbols
# -----------------------------------------------------


def main(sys_argv: list[str]) -> None:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler("pyhex_logs.log")
    file_handler.setLevel(logging.DEBUG)
    logger_formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M.%S")
    file_handler.setFormatter(logger_formatter)
    logger.addHandler(file_handler)
    logger.info("Start logging...")

    try:
        fname: str = sys_argv[FILENAME_POS]
        logger.info("Got filename...")
    except IndexError:
        logger.info("Haven't got filename, exit")
        raise ValueError("not enough arguments.") from None
    perms: tuple[bool, ...] = tuple([access(fname, perm) for perm in (os.F_OK,    # existance
                                                                      os.R_OK,    # readable
                                                                      os.W_OK,    # writeable
                                                                      os.X_OK)])  # executable
    # tbh all perms except writeable and executable can be removed
    # bc anyway if below won't let you further
    if not perms[1]:
        logger.info(f"\"{fname}\" can't be {'read' if perms[0] else 'opened'}, exit")
        raise PermissionError(f"\"{fname}\" can't be {'read' if perms[0] else 'opened'}.")
    file: typing.BinaryIO = open(fname, mode=f"rb{'+' if perms[1] and perms[2] else ''}")
    logger.info(f"Opened \"{fname}\"")
    stdscr = curses.initscr()
    curses.start_color()
    # color_pair(1) - inverted colors
    # color_pair(2) - changed and not selected
    # color_pair(3) - changed and selected
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_WHITE)
    curses.set_tabsize(4)  # this can be removed bc anyway there's won't be any tabs
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
    # [vertical, horizontal, section, second character (only in hex)]
    # section:
    # 0 - hex section
    # 1 - symbols section
    # yeah i know that i can simply use bool or smh but who cares
    cursor: list[int, ...] = [0, 0, 0, 0]
    file_offset: int = 0  # must be file_offset % 16 == 0
    # and yeah, this is also an up left corner
    file_size: int = os.path.getsize(fname)
    curr_encoding: str = "ascii"
    changes: dict = {}
    user_input = 0
    while True:
        logger.debug(f"\n{cursor=}\n{file_offset=}\n{curr_encoding=}\n{changes=}\n")
        stdscr.attron(curses.color_pair(1))
        stdscr.addstr(0, 0, " " * maxx)
        stdscr.addstr(maxy - 1, 0, " " * (maxx - 1))
        stdscr.addstr(0, 2, perms_str)
        stdscr.addstr(0, int((maxx-len(fname)) / 2), f"[{fname}]")
        stdscr.addstr(0, int(maxx-13), "[Modified]" if changes else "")
        stdscr.attroff(curses.color_pair(1))
        absolute_cursor_pos = sum((file_offset, cursor[0] * 16, cursor[1]))

        # added it here because after any input sign "[Saved]" will be erased by code above
        # and if i move input-part here, weird bug appears
        stdscr.addstr(maxy - 1, int(maxx / 2),
                      "[Saved]" if user_input == 19 else "",
                      curses.color_pair(1))

        # this must be optimized
        max_addr_len: int = MIN_ADDR_NUM
        hex_start: str = ''
        for offset in range(file_offset, file_offset+(16*(maxy-1)), 16):
            rjusted_offset: str = (hex(offset))[2:].rjust(len(hex(file_size)) - 2, '0')
            max_addr_len: int = len(rjusted_offset) if len(rjusted_offset) > max_addr_len else max_addr_len
        for line, offset in zip(range(1, maxy - 1), range(file_offset, file_offset+(16*(maxy-1)), 16)):
            # help
            rjusted_offset: str = (hex(offset))[2:].rjust(max_addr_len, '0')
            rjusted_offset = rjusted_offset.upper() if HEX_CAPS else rjusted_offset
            stdscr.addstr(line, 0, hex_start := (rjusted_offset + f"{ADDR_HEX_SEP}"))
        hex_start: int = len(hex_start)  # later this will be hor cords

        file.seek(file_offset, 0)
        spaces_between_hex: int = 0
        for line in range(1, maxy - 1):
            stdscr.move(line, hex_start)
            for block in range(16):
                absolute_print_cursor_pos = sum((file_offset, (line-1)*16, block))
                if absolute_print_cursor_pos not in changes:
                    curr_byte: bytes = file.read(1)
                    color = curses.A_NORMAL if len(curr_byte) else curses.A_DIM
                else:
                    curr_byte: bytes = changes[absolute_print_cursor_pos]
                    file.seek(1, 1)
                    color = curses.color_pair(2)
                hexed_byte: str = curr_byte.hex()
                hexed_byte: str = hexed_byte.upper() if HEX_CAPS else hexed_byte
                stdscr.addstr(hexed_byte if len(hexed_byte) else "..", color)
                stdscr.addstr(" " * SPACES_HEX[sum(counter if block in i
                                                   else 0 for counter, i in enumerate(((1, 13), (3, 11), (5, 9), (7,),
                                                                                       (0, 2, 4, 6, 8, 10, 12, 14))))])
        syms_start: int = sum((hex_start, spaces_between_hex, 45, 3, 2))

        for line in range(1, maxy - 1):
            stdscr.addstr(line, syms_start, f"{HEX_SYM_SEP}")
        syms_start += len(HEX_SYM_SEP)
        file.seek(file_offset, 0)
        for line in range(1, maxy - 1):
            for block in range(16):
                absolute_print_cursor_pos = sum((file_offset, (line - 1) * 16, block))
                if absolute_print_cursor_pos not in changes:
                    curr_byte: bytes = file.read(1)
                    color = curses.A_NORMAL if len(curr_byte) else curses.A_DIM
                else:
                    curr_byte: bytes = changes[absolute_print_cursor_pos]
                    file.seek(1, 1)
                    color = curses.color_pair(2)
                curr_byte: str = curr_byte.decode(curr_encoding, "replace")
                # i found out that it replaces these symbols with 65533
                curr_byte: str = curr_byte if curr_byte.isprintable() else "."
                stdscr.addstr(line, sum((syms_start, block*(len(SYMS_SEP)+1))),
                              curr_byte if len(curr_byte) else ".", color)

        hex_addr_symbol: str = hex(cursor[1])[2]
        stdscr.addstr(1+cursor[0], max_addr_len - 1,
                      hex_addr_symbol.upper() if HEX_CAPS else hex_addr_symbol)
        file.seek(file_offset + (cursor[0] * 16) + cursor[1], 0)
        if absolute_cursor_pos not in changes:
            hexed_byte: bytes = file.read(1)
            color = curses.color_pair(1)
        else:
            hexed_byte: bytes = changes[absolute_cursor_pos]
            color = curses.color_pair(3)
        if not cursor[2]:
            hexed_byte = hexed_byte.hex()
            hexed_byte = hexed_byte.upper() if HEX_CAPS else hexed_byte
            stdscr.addstr(cursor[0]+1, sum((hex_start, cursor[1] * 2,
                                            sum(SPACES_HEX[sum(counter if block in i
                                                else 0 for counter, i in enumerate(((1, 13), (3, 11), (5, 9), (7,),
                                                                                    (0, 2, 4, 6, 8, 10, 12, 14))))]
                                                for block in range(cursor[1])))),
                          hexed_byte if len(hexed_byte) else "..", color)
        else:
            hexed_byte = hexed_byte.decode(curr_encoding, "replace")
            hexed_byte: str = hexed_byte if hexed_byte.isprintable() else "."
            stdscr.addstr(cursor[0]+1, sum((syms_start, cursor[1])),
                          hexed_byte if len(hexed_byte) else ".", color)
        stdscr.attroff(curses.color_pair(3))

        stdscr.refresh()

        user_input = stdscr.getch()
        match user_input:
            case curses.KEY_DOWN:
                if cursor[3]:
                    cursor[3] = 0
                if cursor[0] < maxy - 3:
                    cursor[0] += 1
                else:
                    file_offset += 16
            case curses.KEY_UP:
                if cursor[3]:
                    cursor[3] = 0
                if cursor[0] > 0:
                    cursor[0] -= 1
                elif file_offset > 0:
                    file_offset -= 16
            case curses.KEY_RIGHT:
                if cursor[3]:
                    cursor[3] = 0
                if cursor[1] < 15:
                    cursor[1] += 1
                elif not cursor[2]:
                    cursor[2] = 1
                    cursor[1] = 0
            case curses.KEY_LEFT:
                if cursor[3]:
                    cursor[3] = 0
                if cursor[1] > 0:
                    cursor[1] -= 1
                elif cursor[2]:
                    cursor[2] = 0
                    cursor[1] = 15
            case 24:  # ord(Ctrl+X)
                if len(changes):
                    choice = 0
                    stdscr.addstr(int(maxy/2)-2, int((maxx-45)/2), f"+{'-' * 42}+")
                    stdscr.addstr(int(maxy/2)-1, int((maxx-45)/2), "| Do you want to save changes before exit? |")
                    stdscr.addstr(int(maxy/2), int((maxx-45)/2), f"|{' ' * 42}|")
                    stdscr.addstr(int(maxy/2)+1, int((maxx-45)/2), "|       [Edit]      [No]      [Yes]        |")
                    stdscr.addstr(int(maxy/2)+2, int((maxx-45)/2), f"+{'-' * 42}+")
                    while True:
                        stdscr.addstr(int(maxy / 2) + 1, int(maxx / 2) - 16,
                                      "[Edit]".rjust(7, ">" if not choice
                                                     else " ").ljust(8, "<" if not choice else " "))
                        stdscr.addstr(int(maxy / 2) + 1, int(maxx / 2) - 4,
                                      "[No]".rjust(5, ">" if choice == 1
                                                   else " ").ljust(6, "<" if choice == 1 else " "))
                        stdscr.addstr(int(maxy / 2) + 1, int(maxx / 2) + 6,
                                      "[Yes]".rjust(6, ">" if choice == 2
                                                    else " ").ljust(7, "<" if choice == 2 else " "))
                        user_inp = stdscr.getch()
                        match user_inp:
                            case curses.KEY_RIGHT:
                                choice += 1 if choice < 2 else 0
                            case curses.KEY_LEFT:
                                choice -= 1 if choice > 0 else 0
                            case 10:  # ord(Enter)
                                break
                    if choice == 1:
                        break
                    elif choice == 2:
                        for address, value in changes.items():
                            file.seek(address, 0)
                            file.write(value)
                        break
                else:
                    break
            case 19:  # ord(Ctrl+S)
                logger.debug("user pressed Ctrl+S...")
                changes_copy: dict = changes.copy()
                for address, value in changes.items():
                    file.seek(address, 0)
                    file.write(value)
                    changes_copy.pop(address)
                    logger.debug(f"Saved {value} on {address}")
                changes = changes_copy.copy()
                del changes_copy
            case _:
                pass

        if chr(user_input) in string.hexdigits and not cursor[2]:
            user_input = chr(user_input)
            if absolute_cursor_pos in changes and cursor[3]:
                logger.debug(f"{user_input=}\n{changes[absolute_cursor_pos]=}")
                changes[absolute_cursor_pos] = (int.from_bytes(changes[absolute_cursor_pos],
                                                               byteorder="big", signed=False) +
                                                int(user_input, 16)).to_bytes(1, byteorder="big")
                cursor[3] = 0
            else:
                changes[absolute_cursor_pos] = (int(user_input, 16) * 16).to_bytes(1, byteorder="big")
                cursor[3] = 1
        elif chr(user_input) in string.printable:
            changes[absolute_cursor_pos] = chr(user_input).encode(curr_encoding)
    curses.endwin()
    file.close()


if __name__ == "__main__":
    try:
        main(sys.argv)
    finally:
        curses.endwin()
