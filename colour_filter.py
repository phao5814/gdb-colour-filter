#!/usr/bin/env gdb
#   encoding: utf8
#   file: colour_filter.py

from __future__ import absolute_import
# from typing import Iterator, Text

from gdb import parameter as get_parameter
from gdb import Frame, frame_filters, execute
from gdb.FrameDecorator import FrameDecorator


class FrameColorizer(FrameDecorator):
    u"""FrameColorizer repeats all actions to get all common frame attribute and
    then spices a bit output with colours. Format of output string is following.

    #<depth> <address> in <function> (<frame_args>) at <filename>[:<line>]

    Notes: There is not special support Frame.elided() property.
    """

    def __init__(self, *args, **kwargs):
        if 'depth' in kwargs: depth = kwargs['depth']; del kwargs['depth']
        else: depth = 0
        super(FrameColorizer, self).__init__(*args, **kwargs)

        self._depth = depth
        self.frame = super(FrameColorizer, self).inferior_frame()

    def __str__(self):
        is_print_address = get_parameter(u'print address')

        part1 = self.depth()
        part2 = self.function() + u' \033[1;37m(' + self.frame_args() + u')\033[0m'
        part3 = self.filename() + self.line()

        if is_print_address:
            part1 += u'  ' + self.address() + u' in '
        else:
            part1 += u' '

        parts = part1 + part2 + u' at ' + part3

        screen_width = self.get_screen_width()
        if screen_width is not None and len(parts) > screen_width:
            shift_width = int(self.length(part1)) - 1
            shift_width -= 3 * int(is_print_address)  # compensate ' in ' part
            value = part1 + part2 + u'\n'
            value += u' ' * shift_width + u' at ' + part3
        else:
            value = parts

        return value

    def address(self):
        address = super(FrameColorizer, self).address()
        return u'\033[1;30m0x%016x\033[0m' % address

    def depth(self):
        return u'\033[1;37m#%-3d\033[0m' % self._depth

    def filename(self):
        filename = super(FrameColorizer, self).filename()
        return u'\033[0;36m%s\033[0m' % filename

    def frame_args(self):
        try:
            block = self.frame.block()
        except RuntimeError:
            block = None

        while block is not None:
            if block.function is not None:
                break
            block = block.superblock

        if block is None:
            return u''

        args = []

        for sym in block:
            if not sym.is_argument:
                continue;
            val = sym.value(self.frame)
            arg = u'%s=%s' % (sym, val) if unicode(val) else unicode(sym)
            args.append(arg)

        return u', '.join(args)

    def function(self):
        func = super(FrameColorizer, self).function()

        # GDB could somehow resolve function name by its address.
        # See details here https://cygwin.com/ml/gdb/2017-12/msg00013.html
        if isinstance(func, int):
            # Here we have something like
            # > raise + 272 in section .text of /usr/lib/libc.so.6
            # XXX: gdb.find_pc_line
            symbol = gdb.execute(u'info symbol 0x%016x' % func, False, True)

            # But here we truncate layout in binary
            # > raise + 272
            name = symbol[:symbol.find(u'in section')].strip()

            # Check if we in format
            # > smthing + offset
            parts = name.rsplit(u' ', 1)
            # > raise
            if len(parts) == 1:
                return name

            try:
                offset = hex(int(parts[1]))
            except ValueError:
                return name

            return u'\033[1;34m' + parts[0] + u' ' + offset + u'\033[0m'
        else:
            return u'\033[1;34m' + func + u'\033[0m'

    def get_screen_width(self):
        u"""Get screen width from GDB. Source format is following
        """
        return get_parameter(u'width')

    def line(self):
        value = super(FrameColorizer, self).line()
        return u'\033[0;35m:%d\033[0m' % value if value else u''

    @staticmethod
    def length(colored_string):
        u"""This function calculates length of string with terminal control
        sequences.
        """
        start = 0
        term_seq_len = 0

        while True:
            begin = colored_string.find(u'\033', start)

            if begin == -1:
                break

            end = colored_string.find(u'm', begin)

            if end == -1:
                end = len(s)

            term_seq_len += end - begin + 1
            start = end

        return len(colored_string) - term_seq_len


class FilterProxy(object):
    u"""FilterProxy class keep ensures that frame iterator will be comsumed
    properly on the first and the sole call.
    """

    def __init__(self, frames):
        self.frames = (FrameColorizer(frame, depth=ix)
                       for ix, frame in enumerate(frames))

    def __iter__(self):
        return self

    def next(self):
        self.unroll_stack()
        raise StopIteration

    def unroll_stack(self):
        output = (unicode(frame) for frame in self.frames)
        print u'\n'.join(output)


class ColourFilter(object):

    def __init__(self, name=u'backtrace-filter', priority=0, enabled=True):
        u"""Frame filter with the lower priority that consumes every frame and
        colouring output.

        :param name: The name of the filter that GDB will display.
        :param priority: The priority of the filter relative to other filters.
        :param enabled: A boolean that indicates whether this filter is enabled
        and should be executed.
        """
        self.name = name
        self.priority = priority
        self.enabled = enabled

        # Register this frame filter with the global frame_filters
        # dictionary.
        frame_filters[self.name] = self

    def filter(self, iters):
        return FilterProxy(iters)


ColourFilter()  # register colour filter forcibly