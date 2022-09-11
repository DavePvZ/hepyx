import curses
import encodings
import itertools
import logging
import os
import pkgutil
import re
import string
import struct
import sys  # sus
import typing
from os import access

"""
Hotkeys:
    Ctrl+D - Change endian (from big to little and vice-versa)
    Ctrl+E - Change encoding
    Ctrl+X - Exit
    Ctrl+S - Save
    Ctrl+Z - Undo last change
    Ctrl+F - Find hex or string
    Ctrl+G - Goto
    Ctrl+> - Go to next search result     (aka Ctrl+Shift+.)
    Ctrl+< - Go to previous search result (aka Ctrl+Shift+,)
    Esc    - Clear search query
"""

# ----------------------------------------------------------------------------------------------------------------------
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
# 5 pos - in other cases (1, 3, 5, 7, 9, 11, 13)
HEX_SYM_SEP: str = " | "
# separator between hex nums and symbols
SYMS_SEP: str = ""
# separator between symbols
SYMS_STATS_SEP = " | "
MONOSPACED_65533: bool = False
# In some terminals (or OS? Fonts?), replacement symbol is
# not monospaced (so it breaks the output in some terminals
# (like konsole), but in some not (wsl in windows terminal))
# if false, 65533 will be replaced with REPLACEMENT_CHAR
REPLACEMENT_CHAR: str = "."
# Read comment above
LOGS_ENABLED: bool = False
# Set this to False if you want to compile this with nuitka
# and move this to /bin or if you just don't want logs
LOGGING_LEVEL: int = logging.DEBUG
LOGS_FILENAME: str = "pyhex_logs.log"
LOGS_FORMAT: tuple = ("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M.%S")
# ----------------------------------------------------------------------------------------------------------------------


def main(sys_argv: list[str]) -> None:
    logger = logging.getLogger(__name__)
    logger.setLevel(LOGGING_LEVEL)
    if LOGS_ENABLED:
        file_handler = logging.FileHandler(LOGS_FILENAME)
        logger_formatter = logging.Formatter(*LOGS_FORMAT)
        file_handler.setFormatter(logger_formatter)
        logger.info("Start logging...")
    else:
        file_handler = logging.FileHandler("/dev/null")
        logger.addHandler(file_handler)
    file_handler.setLevel(LOGGING_LEVEL)
    logger.addHandler(file_handler)

    try:
        fname: str = sys_argv[FILENAME_POS]
        logger.info(f"Got filename!")
    except IndexError:
        logger.error(f"Not enought arguments (waited 2, got <2)")
        raise ValueError("not enough arguments.") from None
    perms: tuple[bool, ...] = tuple([access(fname, perm) for perm in (os.F_OK,    # existance
                                                                      os.R_OK,    # readable
                                                                      os.W_OK,    # writeable
                                                                      os.X_OK)])  # executable
    logger.info(f"Permissions: {perms}")
    # tbh all perms except writeable and executable can be removed
    # bc anyway if below won't let you further
    if not perms[1]:
        logger.error(f"\"{fname}\" is not accessible.")
        raise PermissionError(f"\"{fname}\" is not accessible.")
    file: typing.BinaryIO = open(fname, mode=f"rb{'+' if perms[1] and perms[2] else ''}")
    logger.debug(f"Successfully opened \"{fname}\"")
    del fname
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
    logger.debug(f"Screen size: {maxx}x{maxy} lines")
    perms_str: str = f"[{''.join(lttr if perm else '-' for lttr, perm in zip(list('FRWX'), perms))}]"
    # [vertical, horizontal, section, second character (only in hex), search]
    # section:
    # 0 - hex section
    # 1 - symbols section
    cursor: list = [0, 0, False, False, None]
    file_offset: int = 0  # must be file_offset % 16 == 0
    # and yeah, this is also an up left corner
    curr_encoding: str = "ascii"
    curr_endian: bool = True
    # True  - big
    # False - little
    changes: dict = {}
    user_input = 0
    while True:
        stdscr.erase()
        stdscr.attron(curses.color_pair(1))
        stdscr.addstr(0, 0, " " * maxx)
        stdscr.addstr(maxy - 1, 0, " " * (maxx - 1))
        stdscr.addstr(0, 2, perms_str)
        stdscr.addstr(0, 10, f"[{curr_encoding}]")
        stdscr.addstr(0, 14 + len(curr_encoding), f"[{'big' if curr_endian else 'little'}]")
        stdscr.addstr(0, int((maxx-len(file.name)) / 2), f"[{file.name}]")
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
            rjusted_offset: str = (hex(offset))[2:].rjust(len(hex(os.path.getsize(file.name))) - 2, '0')
            max_addr_len: int = len(rjusted_offset) if len(rjusted_offset) > max_addr_len else max_addr_len
        for line, offset in zip(range(1, maxy - 1), range(file_offset, file_offset+(16*(maxy-1)), 16)):
            # help
            rjusted_offset: str = (hex(offset))[2:].rjust(max_addr_len, '0')
            rjusted_offset = rjusted_offset.upper() if HEX_CAPS else rjusted_offset
            stdscr.addstr(line, 0, hex_start := (rjusted_offset + f"{ADDR_HEX_SEP}"))
        hex_start: int = len(hex_start)  # later this will be hor cords
        logger.debug(f"Start of hex section: {hex_start}")

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
                    curr_byte: bytes = changes[absolute_print_cursor_pos][0]
                    file.seek(1, 1)
                    color = curses.color_pair(2)
                hexed_byte: str = curr_byte.hex()
                hexed_byte: str = hexed_byte.upper() if HEX_CAPS else hexed_byte
                stdscr.addstr(hexed_byte if len(hexed_byte) else "..", color)
                stdscr.addstr(" " * SPACES_HEX[sum(counter if block in i
                                                   else 0 for counter, i in enumerate(((1, 13), (3, 11), (5, 9), (7,),
                                                                                       (0, 2, 4, 6, 8, 10, 12, 14))))])
        syms_start: int = sum((hex_start, spaces_between_hex, 45, 3, 2))
        logger.debug(f"Start of symbols section: {syms_start}")

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
                    curr_byte: bytes = changes[absolute_print_cursor_pos][0]
                    file.seek(1, 1)
                    color = curses.color_pair(2)
                curr_byte: str = curr_byte.decode(curr_encoding, "replace")
                curr_byte: str = curr_byte if MONOSPACED_65533 else (REPLACEMENT_CHAR if curr_byte == "�"
                                                                     else curr_byte)
                curr_byte: str = curr_byte if curr_byte.isprintable() else "."
                stdscr.addstr(line, sum((syms_start, block*(len(SYMS_SEP)+1))),
                              curr_byte if len(curr_byte) else ".", color)

        stats_start = syms_start + 16
        for line in range(1, maxy - 1):
            stdscr.addstr(line, stats_start, f"{SYMS_STATS_SEP}")
        stats_start += len(SYMS_STATS_SEP)
        for line, line_value in zip(range(17), [f"{i.ljust(10)}(8 bit):" for i in ("Binary", "Octal", "Hex", "Signed",
                                                                                   "Unsigned")] +
                                    list(itertools.chain.from_iterable([f"{i.ljust(9)}({i_2} bit):" for i
                                                                        in ("Raw", "Signed", "Unsigned")]
                                                                       for i_2 in (2 ** i_3 for i_3 in range(4, 7)))) +
                                    [f"Float    ({i} bit):" for i in (2 ** i for i in range(4, 7))]):
            stdscr.addstr(line + 1, stats_start, line_value)
        stats_start += 19
        line = 1
        file.seek(sum((file_offset, cursor[0] * 16, cursor[1])), 0)
        curr_segment = file.read(8).ljust(8, b"\x00")
        for func, leng in zip((bin, oct), (8, 3)):
            temp = func(curr_segment[0])[2:].rjust(leng, "0")
            stdscr.addstr(line, stats_start, temp.upper() if HEX_CAPS else temp)
            line += 1
        for i, i_2 in zip((2 ** i for i in range(4)), tuple("bhiq")):
            temp = curr_segment[:i][::-1 + int(curr_endian)*2]
            stdscr.addstr(line, stats_start, temp.hex().upper() if HEX_CAPS else temp.hex())
            line += 1
            for signed in (True, False):
                stdscr.addstr(line, stats_start, str(struct.unpack(f">{i_2 if signed else i_2.upper()}",
                                                                   temp)[0]).rjust(len(str(256**i))))
                line += 1
        for i, float_symbol in zip((2 ** i for i in range(1, 4)), tuple("efd")):
            temp = curr_segment[:i][::-1 + int(curr_endian)*2]
            stdscr.addstr(line, stats_start, f"{struct.unpack(f'>{float_symbol}', temp)[0]}")
            line += 1

        find_start = syms_start + len(SYMS_STATS_SEP) + 16
        stdscr.addstr(18, find_start-2, f"+{'-' * (maxx-find_start+1)}")
        # .               ^-----{i think this is not a good idea}-----^
        temp = (cursor[4][0].upper() if HEX_CAPS else cursor[4][0]) if cursor[4] else '_' * 16
        stdscr.addstr(19, find_start, f"Find: {temp}")
        stdscr.addstr(20, find_start, f"""Result: {(cursor[4][1]+1 if cursor[4][2] else '0') if cursor[4]
                                                   else '0'}/{len(cursor[4][2]) if cursor[4]
                                                              else '0'}""")
        del temp

        hex_addr_symbol: str = hex(cursor[1])[2]
        stdscr.addstr(1+cursor[0], max_addr_len - 1,
                      hex_addr_symbol.upper() if HEX_CAPS else hex_addr_symbol)
        file.seek(file_offset + (cursor[0] * 16) + cursor[1], 0)
        if absolute_cursor_pos not in changes:
            hexed_byte: bytes = file.read(1)
            color = curses.color_pair(1)
        else:
            hexed_byte: bytes = changes[absolute_cursor_pos][0]
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
            hexed_byte: str = hexed_byte if MONOSPACED_65533 else (REPLACEMENT_CHAR if hexed_byte == "�"
                                                                   else hexed_byte)
            hexed_byte: str = hexed_byte if hexed_byte.isprintable() else "."
            stdscr.addstr(cursor[0]+1, sum((syms_start, cursor[1])),
                          hexed_byte if len(hexed_byte) else ".", color)

        user_input = stdscr.getch()
        logger.debug(f"User pressed {chr(user_input)} ({user_input})")
        match user_input:
            case curses.KEY_DOWN:
                cursor[3] = False
                if cursor[0] < maxy - 3:
                    cursor[0] += 1
                else:
                    file_offset += 16
            case curses.KEY_UP:
                cursor[3] = False
                if cursor[0] > 0:
                    cursor[0] -= 1
                elif file_offset > 0:
                    file_offset -= 16
            case curses.KEY_RIGHT:
                cursor[3] = False
                if cursor[1] < 15:
                    cursor[1] += 1
                elif not cursor[2]:
                    cursor[2] = not cursor[2]
                    cursor[1] = 0
            case curses.KEY_LEFT:
                cursor[3] = False
                if cursor[1] > 0:
                    cursor[1] -= 1
                elif cursor[2]:
                    cursor[2] = not cursor[2]
                    cursor[1] = 15
            case curses.KEY_HOME:
                file_offset, cursor[:2] = 0, [0, 0]
            case curses.KEY_END:
                temp = os.path.getsize(file.name) - 1
                file_offset, cursor[:2] = temp - (temp % 16), [0, temp % 16]
                del temp
            case 4:  # ord(Ctrl+D)
                curr_endian ^= True
            case 5:  # ord(Ctrl+E)
                encodes = set(name for imp, name, ispkg in pkgutil.iter_modules(encodings.__path__) if not ispkg)
                logger.debug(f"All encodings: {encodes}")
                encodes.difference_update({"aliases"})
                logger.debug(f"Encodings without aliases: {encodes}")
                encodes = tuple(sorted(x for x in encodes
                                       if x not in ("idna", "mbcs", "oem", "palmos", "zlib_codec", "punycode", "rot_13",
                                                    "raw_unicode_escape", "hex_codec", "unicode_escape", "base64_codec",
                                                    "quopri_codec", "bz2_codec", "uu_codec", "undefined")))
                logger.debug(f"Encodings without specifics: {encodes}")
                temp = 0
                # (tuple cursor, cursor)
                encode_cursor = (0, 0)
                for encoding in encodes:
                    temp = temp if temp > len(encoding) else len(encoding)
                temp = int(temp/2) + 2
                stdscr.addstr(1,      int(maxx/2)-temp-2, f"+{'-' * (temp * 2 + 2)}+")
                stdscr.addstr(maxy-2, int(maxx/2)-temp-2, f"+{'-' * (temp * 2 + 2)}+")
                while True:
                    logger.debug(f"Encoding cursor pos: {encode_cursor}")
                    for encoding, line in zip(encodes[encode_cursor[0]:], range(2, maxy-2)):
                        stdscr.addstr(line, int(maxx/2)-temp-2, f"| {encoding.ljust(temp*2)} |")
                    stdscr.addstr(maxy-2, int(maxx/2)+temp-5, f"""[{'↑' if encode_cursor[0] else '-'}|{
                                                                    '-' if encode_cursor[0] == len(encodes)-maxy+4
                                                                    else '↓'}]""")
                    stdscr.addstr(encode_cursor[1]+2, int(maxx/2)-temp-1,
                                  f">{encodes[sum(encode_cursor)]}<", curses.color_pair(1))
                    temp_input = stdscr.getch()
                    logger.debug(f"User Pressed {temp_input}")
                    match temp_input:
                        case curses.KEY_DOWN:
                            if sum(encode_cursor) == len(encodes)-1:
                                pass
                            elif encode_cursor[1] == maxy-5:
                                encode_cursor = (encode_cursor[0]+1, encode_cursor[1])
                            else:
                                encode_cursor = (encode_cursor[0], encode_cursor[1]+1)
                        case curses.KEY_UP:
                            if not sum(encode_cursor):
                                pass
                            elif encode_cursor[1] == 0:
                                encode_cursor = (encode_cursor[0]-1, encode_cursor[1])
                            else:
                                encode_cursor = (encode_cursor[0], encode_cursor[1]-1)
                        case 10:  # ord(Enter)
                            temp = curr_encoding
                            curr_encoding = encodes[sum(encode_cursor)]
                            break
                        case 27:
                            break
                logger.debug(f"Changed {temp} encoding to {curr_encoding}")
                del encodes, encode_cursor, temp
            case 6:  # ord(Ctrl+F)
                temp = ["", False]
                # False - hex
                # True  - symbols
                """
                +----------------------------------+
                | Find this in hex section:        |
                | ________________________________ |
                +----------------------------------+
                """
                for line, line_value in zip(range(-2, 2), (f"+{'-' * 34}+", "| Find this in hex section:        |",
                                                           f"| {'_' * 32} |", f"+{'-' * 34}+")):
                    stdscr.addstr(int(maxy / 2) + line, int(maxx / 2) - 18, line_value)
                while True:
                    stdscr.addstr(int(maxy / 2), int(maxx / 2) - 16, temp[0].upper() if HEX_CAPS and not temp[1]
                                  else temp[0])
                    stdscr.addstr(int(maxy / 2) + 1, int(maxx / 2)-16, "{[Text]}" if temp[1] else "{[Hex]}-")
                    stdscr.addstr(int(maxy / 2), int(maxx / 2) - 16 + len(temp[0]), "_" * (32 - len(temp[0])))
                    stdscr.addstr(int(maxy / 2), int(maxx / 2) + 16, " ")
                    # .           ^--{ absolutely not a workaround }--^
                    stdscr.addstr(int(maxy / 2), int(maxx / 2) - 16 + len(temp[0]), "_" if len(temp[0]) < 32 else " ",
                                  curses.color_pair(1))

                    temp_input = stdscr.getch()
                    stdscr.addstr(int(maxy / 2) - 1, int(maxx / 2) - 16, "Find this in hex section:      ")
                    stdscr.addstr(int(maxy / 2) + 1, int(maxx / 2) + 1, '-' * 15)
                    logger.debug(f"{temp=}")
                    match temp_input:
                        case curses.KEY_UP:
                            temp = [temp[0] if not temp[1] else "", False]
                        case curses.KEY_DOWN:
                            temp = [temp[0] if temp[1] else "", True]
                        case 10:  # ord(Enter)
                            if len(temp[0]) % 2 and not temp[1]:
                                """
                                +----------------------------------+
                                | Given hex num's len is not even  |
                                | ________________________________ |
                                +------------------(Press any key)-+
                                """
                                for line, col, line_value in zip((-1, 1), (16, -1), ("Given hex num's len is not even",
                                                                                     "(Press any key)")):
                                    stdscr.addstr(int(maxy / 2) + line, int(maxx / 2) - col, line_value)
                            elif len(temp[0]):
                                if temp[1]:
                                    temp[0] = temp[0].encode(curr_encoding).hex()
                                cursor[4] = [temp[0], 0, []]
                                temp = re.compile(temp[0].replace("?", "[0-9a-f]?"))
                                for i in range(os.path.getsize(file.name)):
                                    file.seek(i, 0)
                                    if re.match(temp, file.read(int(len(cursor[4][0])/2)).hex()):
                                        cursor[4][2] += [i]
                                del temp
                                break
                        case 27:  # ord(Esc)
                            break
                        case 263:  # ord(Backspace)
                            temp[0] = temp[0][:-1]
                        case _:
                            if chr(temp_input) in f"{string.hexdigits}?" and not temp[1]:
                                temp[0] += chr(temp_input) if len(temp[0]) < 32 else ""
                            elif chr(temp_input) in string.printable.replace(string.whitespace, "") + " " and temp[1]:
                                temp[0] += chr(temp_input) if len(temp[0]) < 32 else ""
            case 7:  # ord(Ctrl+G)
                temp = ""
                """
                +------------------+
                | Go to address:   |
                | ________________ |
                +------------------+
                """
                for line, line_value in zip(range(-2, 2), (f"+{'-'*18}+", "| Go to address:   |",
                                                           f"| {'_'*16} |", f"+{'-' * 18}+")):
                    stdscr.addstr(int(maxy/2)+line, int(maxx/2)-10, line_value)
                while True:
                    logger.debug(f"Goto address: \"{temp}\"")
                    stdscr.addstr(int(maxy/2), int(maxx/2)-8, temp.upper() if HEX_CAPS else temp)
                    stdscr.addstr(int(maxy/2), int(maxx/2)-7+len(temp), "_" * (15-len(temp)))
                    stdscr.addstr(int(maxy / 2), int(maxx / 2)+8, " ")
                    # .           ^-{ absolutely not a workaround }-^
                    stdscr.addstr(int(maxy/2), int(maxx/2)-8+len(temp), "_" if len(temp) < 16 else " ",
                                  curses.color_pair(1))

                    temp_input = stdscr.getch()
                    logger.debug(f"User pressed {temp_input}")
                    match temp_input:
                        case 10:  # ord(Enter)
                            if len(temp):
                                temp = int(temp, 16)
                                file_offset, cursor[0], cursor[1] = (temp - temp % 16, 0, temp % 16)
                                break
                        case 27:  # ord(Esc)
                            break
                        case 263:  # ord(Backspace)
                            temp = temp[:-1]
                        case _:
                            if chr(temp_input) in string.hexdigits and len(temp) < 16:
                                temp += chr(temp_input)
                if temp_input in (10, 27):
                    del temp
            case 19:  # ord(Ctrl+S)
                temp = changes.copy()
                for address, value in changes.items():
                    file.seek(address, 0)
                    file.write(value[0])
                    temp.pop(address)
                changes = temp.copy()
                del temp
            case 24:  # ord(Ctrl+X)
                if len(changes):
                    choice = 0
                    for line, line_value in zip(range(-2, 3),
                                                (f"+{'-' * 42}+", "| Do you want to save changes before exit? |",
                                                 f"|{' ' * 42}|", "|       [Edit]      [No]      [Yes]        |",
                                                 f"+{'-' * 42}+")):
                        stdscr.addstr(int(maxy/2)+line, int((maxx-45)/2), line_value)
                    while True:
                        logger.debug(f"User's choice: {choice}")
                        for offset, button, choice_var in zip((-16, -4, 6), ("[Edit]", "[No]", "[Yes]"), range(3)):
                            stdscr.addstr(int(maxy / 2) + 1, int(maxx / 2) + offset,
                                          button.rjust(len(button)+1, ">" if choice == choice_var
                                                       else " ").ljust(len(button)+2,
                                                                       "<" if choice == choice_var else " "))
                        temp_input = stdscr.getch()
                        logger.debug(f"User's input: {temp_input}")
                        match temp_input:
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
                            file.write(value[0])
                        break
                    del temp_input
                else:
                    break
            case 26:  # ord(Ctrl+Z)
                temp = (-1, -1)
                for address, value in changes.items():
                    temp = temp if temp[1] > value[1] else (address, value[1])
                if temp[1] != -1:
                    del changes[temp[0]], temp
            case 27:  # ord(Esc)
                cursor[4] = None
            case 44:  # ord(Ctrl+<)
                cursor[4][1] -= int(cursor[4][1] > 0)
                if len(cursor[4][2]):
                    temp = cursor[4][2][cursor[4][1]]
                    file_offset = temp - temp % 16
                    cursor[:2] = [0, temp % 16]
                    del temp
            case 46:  # ord(Ctrl+>)
                cursor[4][1] += int(cursor[4][1] < len(cursor[4][2])-1)
                if len(cursor[4][2]):
                    temp = cursor[4][2][cursor[4][1]]
                    file_offset = temp - temp % 16
                    cursor[:2] = [0, temp % 16]
                    del temp
            case _:
                user_input = chr(user_input)
                if user_input in string.hexdigits and not cursor[2]:
                    if cursor[3]:
                        changes[absolute_cursor_pos] = ((int(user_input, 16) +
                                                         int.from_bytes(changes[absolute_cursor_pos][0],
                                                                        byteorder="big")).to_bytes(1, byteorder="big",
                                                                                                   signed=False),
                                                        changes[absolute_cursor_pos][1])
                        cursor[3] = False
                    else:
                        temp = sorted(i[1] for i in changes.values())
                        temp = temp[-1] if len(temp) else 0
                        changes[absolute_cursor_pos] = ((int(user_input, 16)*16).to_bytes(1, byteorder="big",
                                                                                          signed=False),
                                                        temp)
                        cursor[3] = True
                        del temp
                elif cursor[2]:
                    temp = sorted(i[1] for i in changes.values())
                    temp = temp[-1] if len(temp) else 0
                    changes[absolute_cursor_pos] = (user_input.encode(encoding=curr_encoding,
                                                                      errors="replace"),
                                                    temp)
                    cursor[3] = True
                    del temp
                if not cursor[3]:
                    temp = changes.copy()
                    for address, value in changes.items():
                        file.seek(address, 0)
                        if file.read(1) == value[0]:
                            temp.pop(address)
                    changes = temp.copy()
                    del temp
    curses.endwin()
    file.close()


if __name__ == "__main__":
    try:
        main(sys.argv)
    finally:
        curses.endwin()
