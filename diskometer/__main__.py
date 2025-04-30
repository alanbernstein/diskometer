#!/usr/bin/env python3
import curses
import datetime
import json
import os
import subprocess
import sys
import time

from colorama import Fore, Back, Style

from ipdb import set_trace as db, iex

@iex
def main():
    if '-f' in sys.argv:
        curses.wrapper(draw_meter)
    else:
        print_df_result_colorama(get_df_result())


def draw_meter(stdscr):
    # Clear and refresh the screen for a blank canvas
    stdscr.clear()
    stdscr.refresh()

    # Start colors in curses
    curses.start_color()
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)

    k = 0
    status_str = ''

    first_run = True

    size_mode_list = ['proportional', 'fill']
    size_mode_idx = 0
    size_mode = size_mode_list[size_mode_idx]

    messages = []

    res_prev = os.get_terminal_size()
    while (k != ord('q')):
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        redraw = False

        if first_run:
            redraw = True
        first_run = False

        res = os.get_terminal_size()
        if res != res_prev:
            messages.append('resize to %s x %s' % (height, width))
            redraw = True
        res_prev = res

        if k == ord('m'):
            redraw = True
            size_mode_idx = (size_mode_idx + 1) % len(size_mode_list)
            size_mode = size_mode_list[size_mode_idx]
            status_str = '"m": size mode = %s' % size_mode
            messages.append(status_str)

        if redraw:

            timestamp = datetime.datetime.strftime(datetime.datetime.now(), '%m/%d %H:%M:%S')
            stdscr.addstr(0, 0, timestamp)

            # disk space meters
            df_result = get_df_result()

            print_df_result_curses(stdscr, df_result, size_mode)

            # other meters?
            # cpu and mem usage?
            #

            stdscr.attron(curses.color_pair(3))
            stdscr.addstr(height-1, 0, status_str)
            stdscr.addstr(height-1, len(status_str), " " * (width - len(status_str) - 1))
            stdscr.attroff(curses.color_pair(3))


        # Refresh the screen
        stdscr.refresh()

        # Wait for next input
        k = stdscr.getch()

    for m in messages:
        print(m)


ignore_list = ['/boot/efi', '/sys/firmware/efi/efivars']

df_keys = ['device_path', 'fstype', 'size', 'used', 'avail', 'used_pct', 'root_mount']
widths = [14, 7, 5, 5, 5, 4, 20]  # manually determined from output of `df`
fmtstr = ' '.join(['%%%ss' % w for w in widths])

def print_df_result_curses(stdscr, df_disks, size_mode=None):
    size_mode = size_mode or 'proportional'  # or 'fill'

    res = os.get_terminal_size()
    W, H = res.columns, res.lines
    #print('%d columns' % W)

    h = human_readable

    # compute bar width
    max_nonbar_width = 0
    max_size = 0
    for disk in df_disks:
        use_ratio = disk['used'] / disk['size']
        pre_str = '%4.1f%% %10s' % (100*use_ratio, h(disk['size']))
        post_str = '| %10s %14s %s' % (h(disk['avail']), disk['device_path'], disk['root_mount'])
        nonbar_width = 2 + len(pre_str) + len(post_str)
        max_nonbar_width = max(nonbar_width, max_nonbar_width)
        max_size = max(disk['size'], max_size)

    # print header
    bar_width = W - max_nonbar_width  # need some checks here
    pre_str = '%4s %10s   %12s' % ('use', 'size', size_mode)
    post_str = '  %10s' % ('free')
    s = pre_str + ' ' * (bar_width-15) + post_str
    stdscr.addstr(1, 0, s)

    # print usage bars
    df_disks.sort(key=lambda x: x['size'])
    # TODO use two different scales, for <500GB and >=500GB
    for n, disk in enumerate(df_disks, start=2):
        use_ratio = disk['used'] / disk['size']
        color = Back.GREEN
        if disk['avail'] < 10e6 or use_ratio > .95:
            color = Back.RED
        pre_str = '%4.1f%% %10s ' % (100*use_ratio, h(disk['size']))
        post_str = '%10s %-14s %20s' % (h(disk['avail']), disk['device_path'], disk['root_mount'])

        if size_mode == 'fill':
            used_count = int(use_ratio * bar_width)
            free_count = bar_width - used_count
            pad_count = 0
        elif size_mode == 'proportional':
            bytes_per_column = max_size / bar_width
            used_count = int(disk['used'] / bytes_per_column)
            free_count = int(disk['avail'] / bytes_per_column)
            pad_count = W - 2 - len(pre_str + post_str) - used_count - free_count

        # db()

        #bar = '|' + Fore.BLACK + color + ' ' * used_count + Fore.WHITE + Back.BLACK + ' ' * free_count + Style.RESET_ALL + '|' + ' ' * pad_count
        bar = '|' + ' ' * used_count + ' ' * free_count + '|' + ' ' * pad_count

        s = pre_str + bar + post_str
        stdscr.addstr(n, 0, s)



def print_df_result(df_disks):
    for disk in df_disks:
        print(disk)

def print_df_result_nice(df_disks):
    db()
    print(fmtstr % tuple(df_keys))
    for disk in df_disks:
        print(fmtstr % tuple(disk.values()))
    pass

def print_df_result_colorama(df_disks, size_mode=None):
    size_mode = size_mode or 'proportional'  # or 'fill'

    res = os.get_terminal_size()
    W, H = res.columns, res.lines
    #print('%d columns' % W)

    h = human_readable

    # compute bar width
    max_nonbar_width = 0
    max_size = 0
    max_chars = {}
    max_chars['use'] = len('83.6%')
    columns = [
        {
            'title': 'mount',
            'max_chars': 20,
            'fmt': '%-20s',
            'tfmt': '%-20s',
        }, {
            'title': 'device',
            'max_chars': 14,
            'fmt': '%14s',
            'tfmt': '%14s',
        }, {
            'title': 'size',
            'max_chars': 10,
            'fmt': '%10s',
            'tfmt': '%10s',
        }, {
            'title': 'free',
            'max_chars': 10,
            'fmt': '%10s',
            'tfmt': '%10s',
        }, {
            'title': 'use',
            'max_chars': 7,
            'fmt': ' %4.1f%% ',
            'tfmt': ' %5s ',
        }, {
            'title': size_mode,
            'max_chars': -1,  # variable
            'fmt': None, # special case
            'tfmt': '%-12s',
        }
    ]

    for disk in df_disks:
        use_ratio = disk['used'] / disk['size']
        pre_str = '%4.1f%% %10s' % (100*use_ratio, h(disk['size']))
        post_str = '| %10s %14s %s' % (h(disk['avail']), disk['device_path'], disk['root_mount'])
        max_size = max(disk['size'], max_size)

    max_nonbar_width = 1  # +1 is a fudge factor
    pre_str_fmt = ''
    title_fmt = ''
    title_vals = []
    for c in columns:
        if c['max_chars'] > 0:
            max_nonbar_width += c['max_chars']
        if c['fmt']:
            pre_str_fmt += c['fmt']
        if c['tfmt']:
             title_fmt += c['tfmt']
             title_vals.append(c['title'])
            
    # print header
    print(title_fmt % tuple(title_vals))

    # print usage bars
    bar_width = W - max_nonbar_width  # need some checks here
    df_disks.sort(key=lambda x: x['size'])
    # TODO use two different scales, for <500GB and >=500GB
    for disk in df_disks:
        use_ratio = disk['used'] / disk['size']
        color = Back.GREEN
        if disk['avail'] < 10e6 or use_ratio > .95:
            color = Back.RED
        pre_str = pre_str_fmt % (disk['root_mount'], disk['device_path'], h(disk['size']), h(disk['avail']), 100*use_ratio)
        post_str = ''

        if size_mode == 'fill':
            used_count = int(use_ratio * bar_width)
            free_count = bar_width - used_count
            pad_count = 0
        elif size_mode == 'proportional':
            bytes_per_column = max_size / bar_width
            used_count = int(disk['used'] / bytes_per_column)
            free_count = int(disk['avail'] / bytes_per_column)
            pad_count = W - 2 - len(pre_str + post_str) - used_count - free_count

        bar = '|' + Fore.BLACK + color + ' ' * used_count + Fore.WHITE + Back.BLACK + ' ' * free_count + Style.RESET_ALL + '|' + ' ' * pad_count
        s = pre_str + bar + post_str
        print(s)


def colorama_progressbar(capacity, used, bar_width):
    pct_use = used / capacity
    free = capacity - used
    pre_str = '%d%% %s |' % (pct_use, capacity)
    post_str = '| %s free %14s %s' % (free, 'foo', 'bar')
    nonbar_width = len(pre_str) + len(post_str)


    res = os.get_terminal_size()
    columns, lines = res.columns, res.lines
    if bar_width==0: # 'auto'
        bar_width = columns - nonbar_width

    used_count = int(pct_use * bar_width)
    free_count = bar_width - used_count
    bar = Fore.BLACK + Back.GREEN + ' ' * used_count + Fore.WHITE + Back.BLACK + ' ' * free_count + Style.RESET_ALL
    s = pre_str + bar + post_str

    print(s)



def human_readable(d):
    if d < 1000:
        s = "%3fK" % d
    elif d < 1000000:
        s = "%3.1fM" % (d/1024)
    elif d < 1000000000:
        s = "%3.1fG" % (d/1024**2)
    else:
        s = '%3.1fT' % (d/1024**3)
    return s


def get_df_result():
    ignore_fs = ['squashfs', 'tmpfs', 'devtmpfs']
    ignore_cmd_fragment = ' ' .join(['-x %s' % f for f in ignore_fs])
    df_cmd = 'df -T %s' % ignore_cmd_fragment

    try:
        output = subprocess.check_output(df_cmd, shell=True)
    except Exception as exc:
        print(exc)
        db()
    lines = output.strip().decode('utf-8').split('\n')

    disks = []
    for line in lines:
        parts = line.split()
        parts[6] = ' '.join(parts[6:]) # last column is name, could have any number of spaces in it
        disk = dict(zip(df_keys, parts))

        if disk['fstype'] == 'Type':
            continue
        if disk['root_mount'] in ignore_list:
            continue

        disk['size'] = int(disk['size'])
        disk['used'] = int(disk['used'])
        disk['avail'] = int(disk['avail'])
        disk['used_pct'] = int(disk['used_pct'][:-1])
        disks.append(disk)

    return disks


if __name__ == '__main__':
    main()
