__revision__ = "$Id$"

# ----------- this is copied from distutils.fancy_getopt to eliminate
#             dependency on python-dev package in Debian:
import string, re

WS_TRANS = string.maketrans(string.whitespace, ' ' * len(string.whitespace))
def wrap_text (text, width):
    """wrap_text(text : string, width : int) -> [string]

    Split 'text' into multiple lines of no more than 'width' characters
    each, and return the list of strings that results.
    """

    if text is None:
        return []
    if len(text) <= width:
        return [text]

    text = string.expandtabs(text)
    text = string.translate(text, WS_TRANS)
    chunks = re.split(r'( +|-+)', text)
    chunks = filter(None, chunks)      # ' - ' results in empty strings
    lines = []

    while chunks:

        cur_line = []                   # list of chunks (to-be-joined)
        cur_len = 0                     # length of current line

        while chunks:
            l = len(chunks[0])
            if cur_len + l <= width:    # can squeeze (at least) this chunk in
                cur_line.append(chunks[0])
                del chunks[0]
                cur_len = cur_len + l
            else:                       # this line is full
                # drop last chunk if all space
                if cur_line and cur_line[-1][0] == ' ':
                    del cur_line[-1]
                break

        if chunks:                      # any chunks left to process?

            # if the current line is still empty, then we had a single
            # chunk that's too big too fit on a line -- so we break
            # down and break it up at the line width
            if cur_len == 0:
                cur_line.append(chunks[0][0:width])
                chunks[0] = chunks[0][width:]

            # all-whitespace chunks at the end of a line can be discarded
            # (and we know from the re.split above that if a chunk has
            # *any* whitespace, it is *all* whitespace)
            if chunks[0][0] == ' ':
                del chunks[0]

        # and store this line in the list-of-all-lines -- as a single
        # string, of course!
        lines.append(string.join(cur_line, ''))

    # while chunks

    return lines

# wrap_text ()


class HelpFormatter:

    """
    Abstract base class for formatting option help.  OptionParser
    instances should use one of the HelpFormatter subclasses for
    formatting help; by default IndentedHelpFormatter is used.

    Instance attributes:
      indent_increment : int
        the number of columns to indent per nesting level
      max_help_position : int
        the maximum starting column for option help text
      help_position : int
        the calculated starting column for option help text;
        initially the same as the maximum
      width : int
        total number of columns for output
      level : int
        current indentation level
      current_indent : int
        current indentation level (in columns)
      help_width : int
        number of columns available for option help text (calculated)
    """

    def __init__ (self,
                  indent_increment,
                  max_help_position,
                  width,
                  short_first):
        self.indent_increment = indent_increment
        self.help_position = self.max_help_position = max_help_position
        self.width = width
        self.current_indent = 0
        self.level = 0
        self.help_width = width - max_help_position
        if short_first:
            self.format_option_strings = self.format_option_strings_short_first
        else:
            self.format_option_strings = self.format_option_strings_long_first

    def indent (self):
        self.current_indent += self.indent_increment
        self.level += 1

    def dedent (self):
        self.current_indent -= self.indent_increment
        assert self.current_indent >= 0, "Indent decreased below 0."
        self.level -= 1

    def format_usage (self, usage):
        raise NotImplementedError, "subclasses must implement"

    def format_heading (self, heading):
        raise NotImplementedError, "subclasses must implement"

    def format_description (self, description):
        desc_width = self.width - self.current_indent
        desc_lines = wrap_text(description, desc_width)
        result = ["%*s%s\n" % (self.current_indent, "", line)
                  for line in desc_lines]
        return "".join(result)

    def format_option (self, option):
        # The help for each option consists of two parts:
        #   * the opt strings and metavars
        #     eg. ("-x", or "-fFILENAME, --file=FILENAME")
        #   * the user-supplied help string
        #     eg. ("turn on expert mode", "read data from FILENAME")
        #
        # If possible, we write both of these on the same line:
        #   -x      turn on expert mode
        #
        # But if the opt string list is too long, we put the help
        # string on a second line, indented to the same column it would
        # start in if it fit on the first line.
        #   -fFILENAME, --file=FILENAME
        #           read data from FILENAME
        result = []
        opts = option.option_strings
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = "%*s%s\n" % (self.current_indent, "", opts)
            indent_first = self.help_position
        else:                       # start help on same line as opts
            opts = "%*s%-*s  " % (self.current_indent, "", opt_width, opts)
            indent_first = 0
        result.append(opts)
        if option.help:
            help_lines = wrap_text(option.help, self.help_width)
            result.append("%*s%s\n" % (indent_first, "", help_lines[0]))
            result.extend(["%*s%s\n" % (self.help_position, "", line)
                           for line in help_lines[1:]])
        elif opts[-1] != "\n":
            result.append("\n")
        return "".join(result)

    def store_option_strings (self, parser):
        self.indent()
        max_len = 0
        for opt in parser.option_list:
            strings = self.format_option_strings(opt)
            opt.option_strings = strings
            max_len = max(max_len, len(strings) + self.current_indent)
        self.indent()
        for group in parser.option_groups:
            for opt in group.option_list:
                strings = self.format_option_strings(opt)
                opt.option_strings = strings
                max_len = max(max_len, len(strings) + self.current_indent)
        self.dedent()
        self.dedent()
        self.help_position = min(max_len + 2, self.max_help_position)

    def format_option_strings (self, option):
        """Return a comma-separated list of option strings & metavariables."""
        raise NotImplementedError(
            "abstract method: use format_option_strings_short_first or "
            "format_option_strings_long_first instead.")

    def format_option_strings_short_first (self, option):
        opts = []                       # list of "-a" or "--foo=FILE" strings
        takes_value = option.takes_value()
        if takes_value:
            metavar = option.metavar or option.dest.upper()
            for sopt in option._short_opts:
                opts.append(sopt + metavar)
            for lopt in option._long_opts:
                opts.append(lopt + "=" + metavar)
        else:
            for opt in option._short_opts + option._long_opts:
                opts.append(opt)
        return ", ".join(opts)

    def format_option_strings_long_first (self, option):
        opts = []                       # list of "-a" or "--foo=FILE" strings
        takes_value = option.takes_value()
        if takes_value:
            metavar = option.metavar or option.dest.upper()
            for lopt in option._long_opts:
                opts.append(lopt + "=" + metavar)
            for sopt in option._short_opts:
                opts.append(sopt + metavar)
        else:
            for opt in option._long_opts + option._short_opts:
                opts.append(opt)
        return ", ".join(opts)


class IndentedHelpFormatter (HelpFormatter):
    """Format help with indented section bodies.
    """

    def __init__ (self,
                  indent_increment=2,
                  max_help_position=24,
                  width=80,
                  short_first=1):
        HelpFormatter.__init__(
            self, indent_increment, max_help_position, width, short_first)

    def format_usage (self, usage):
        return "usage: %s\n" % usage

    def format_heading (self, heading):
        return "%*s%s:\n" % (self.current_indent, "", heading)


class TitledHelpFormatter (HelpFormatter):
    """Format help with underlined section headers.
    """

    def __init__ (self,
                  indent_increment=0,
                  max_help_position=24,
                  width=80,
                  short_first=0):
        HelpFormatter.__init__ (
            self, indent_increment, max_help_position, width, short_first)

    def format_usage (self, usage):
        return "%s  %s\n" % (self.format_heading("Usage"), usage)

    def format_heading (self, heading):
        return "%s\n%s\n" % (heading, "=-"[self.level] * len(heading))
