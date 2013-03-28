# Copyright 2010-2013 Zack Weinberg <zackw@panix.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the Artistic License 2.0.  See the file
# "Artistic-2.0" in the source distribution, or
# <http://www.opensource.org/licenses/artistic-license-2.0.php>, for
# further details.

# Parser for PDF content streams.  Note that, sadly, this *does* need
# to handle arrays and dictionaries; despite the elaborate mechanism
# for keeping composite objects out of content streams, some of them
# do appear.

# PDF is defined in terms of bytes, therefore we comprehensively avoid
# Unicode strings below.

import re

class PDFSyntaxError(Exception): pass

# utilities might get pulled out to another file later

class PushbackIterator(object):
    """Wrap some other iterator (or iterable) and provide a pushback
    mechanism.  We need two items' worth of pushback under some
    circumstances, so this allows an unbounded, LIFO pushback queue."""
    def __init__(self, it):
        self._it = iter(it)
        self._pushback = []

    def __iter__(self): return self

    def __next__(self):
        if len(self._pushback) > 0:
            return self._pushback.pop()
        else:
            return next(self._it)

    def pushback(self, item):
        self._pushback.append(item)

# PDF does not support exponential notation.  There is no convenient
# way to suppress exponential notation without also fixing the number
# of digits after the decimal point, so the best available approach
# is to use str() to get a compact value-preserving representation and
# then disassemble it and reconstitute a purely place-value representation.

_ftod_r = re.compile(
    br'^(-?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-][0-9]+))?$')
def ftod(f):
    """Print a floating-point number in the format expected by PDF:
    as short as possible, no exponential notation."""
    s = bytes(str(f), 'ascii')
    m = _ftod_r.match(s)
    if not m:
        raise RuntimeError("unexpected floating point number format: {!a}"
                           .format(s))
    sign = m.group(1)
    intpart = m.group(2)
    fractpart = m.group(3)
    exponent = m.group(4)
    if ((intpart is None or intpart == b'') and
        (fractpart is None or fractpart == b'')):
        raise RuntimeError("unexpected floating point number format: {!a}"
                           .format(s))

    # strip leading and trailing zeros
    if intpart is None: intpart = b''
    else: intpart = intpart.lstrip(b'0')
    if fractpart is None: fractpart = b''
    else: fractpart = fractpart.rstrip(b'0')

    if intpart == b'' and fractpart == b'':
        # zero or negative zero; negative zero is not useful in PDF
        # we can ignore the exponent in this case
        return b'0'

    # convert exponent to a decimal point shift
    elif exponent is not None:
        exponent = int(exponent)
        exponent += len(intpart)
        digits = intpart + fractpart
        if exponent <= 0:
            return sign + b'.' + b'0'*(-exponent) + digits
        elif exponent >= len(digits):
            return sign + digits + b'0'*(exponent - len(digits))
        else:
            return sign + digits[:exponent] + b'.' + digits[exponent:]

    # no exponent, just reassemble the number
    elif fractpart == b'':
        return sign + intpart # no need for trailing dot
    else:
        return sign + intpart + b'.' + fractpart

def gen_paren_string(s):
    """Produce a parenthesized string in the style expected by PDF.
    We take full advantage of the rule that "any characters may appear
    in a string except unbalanced parentheses and the backslash"
    without being escaped."""

    # First double all existing backslashes.
    s = re.sub(br'\\', br'\\\\', s)

    # Parentheses are a little trickier since we wish to use the
    # license to leave balanced parentheses unescaped.  For now, just
    # count parentheses and if they aren't balanced, backwhack them all.
    depth = 0
    for c in s:
        if c == b'(': depth += 1
        elif c == b')': depth -= 1
    if depth != 0:
        s = re.sub(b"[()]", br"\\\g<0>", s)
    return b'(' + s + b')'

# serialize() handles the slight differences between Python's and PDF's
# printable representation of numbers, strings, booleans, and the null object.
def serialize(obj):
    if obj is None: return b'null'
    elif obj is True: return b'true'
    elif obj is False: return b'false'
    elif isinstance(obj, float): return ftod(obj)
    elif isinstance(obj, bytes): return gen_paren_string(obj)
    else:
        try: return obj.serialize()
        except TypeError: return str(obj)

# Identifiers.

_escape_id_r = re.compile(br'[\x00-\x20()<>\[\]{}/%#\x7F-\xFF]')
def _escape_id(text):
    return re.sub(_escape_id_r, 
                  lambda m: bytes('#{:02X}'.format(ord(m.group(0))),
                                  "us-ascii"),
                  text)

_unescape_id_r = re.compile(br'#([0-9a-fA-F]{2})')
def _unescape_id(text):
    def unesc1(m):
        if m.group(1) is not None:
            return bytes((int(m.group(1), 16),))
        raise PDFSyntaxError("invalid #-notation in id {!a}".format(repr(text)))
    return re.sub(_unescape_id_r, unesc1, text)

class Id(bytes):
    """An Id is an interned string, normally complying with PDF's
    rules for identifier syntax.  It does not include the leading /
    if any.  Note: the *caller* of Id() is responsible for
    unescaping #-notation."""

    def __new__(cls, *args, **kwargs):
        text = super(Id, cls).__new__(cls, *args, **kwargs)
        return cls.syms.setdefault(text, text)

    def __repr__(self):
        return "Id(" + super(Id, self).__repr__() + ")"

    def serialize(self):
        return _escape_id(self)

class Name(Id):
    """A literal name (/Name in the input notation)."""
    syms = {}

    def serialize(self):
        return b'/' + super(Name, self).serialize()

class Operator(Id):
    """An operator - has some effect."""
    syms = {}

# Thin wrappers around array and dict which handle the two kinds of each
# and producing the PDF printable representation.

class Array(list):
    def serialize(self):
        return b'[' + b' '.join(serialize(x) for x in self) + b']'

    def __repr__(self):
        return "Array(" + super(Array, self).__repr__() + ")"

class CArray(list):
    def serialize(self):
        return b'{ ' + b' '.join(serialize(x) for x in self) + b' }'

    def __repr__(self):
        return "CArray(" + super(CArray, self).__repr__() + ")"

class Dict(dict):
    def serialize(self):
        return b'<< ' + b' '.join(serialize(k)+b' '+serialize(v) 
                                  for k, v in self.items()) + b' >>'
    def __repr__(self):
        return "Dict(" + super(Dict, self).__repr__() + ")"

class IIDict(dict):
    def serialize(self):
        return b'BI ' + b' '.join(serialize(k)+b' '+serialize(v) 
                                  for k, v in self.items()) + b' ID'
    def __repr__(self):
        return "IIDict(" + super(Dict, self).__repr__() + ")"

# "Core syntax" tokens are represented as operators.
_array_begin = Operator(b'[')
_array_end = Operator(b']')
_carray_begin = Operator(b'{')
_carray_end = Operator(b'}')
_dict_begin = Operator(b'<<')
_dict_end = Operator(b'>>')

# Inline image operators are not really core syntax, but their nested
# stream semantic means we have to know about them here anyway.
_image_begin = Operator(b'BI')
_image_data = Operator(b'ID')
_image_end = Operator(b'EI')

# All PDF numbers match this regular expression.
_number_r = re.compile(br'^[+-]?(?:[0-9]+\.?|[0-9]*\.[0-9]+)$')

class ContentParser(object):
    """A ContentParser is an iterator over an object which, when
    itself iterated, yields single bytes.  The ContentParser yields
    complete content-stream objects, which are ordinary Python objects
    when there is a direct analogue (booleans, numbers, strings,
    arrays, dicts) or custom classes otherwise (names, operators,
    inline images)."""

    def __init__(self, data):
        self._data = PushbackIterator(data)

    def __iter__(self): return self

    def __next__(self):
        self.skip_whitespace_and_comments()
        p = self._data
        c = next(p)

        if c == b'/': return self.parse_name_literal()
        if c == b'(': return self.parse_paren_string()
        if c == b'[': return self.parse_array(False)
        if c == b'{': return self.parse_array(True)

        if c == b'<':
            c = next(p)
            if c == b'<':
                return self.parse_dict(False)
            elif c in b'0123456789ABCDEFabcdef \t\r\n\f':
                p.pushback(c)
                return self.parse_hex_string()
            else:
                raise PDFSyntaxError("Invalid hexadecimal string - "
                                     "begins with {!a}".format(c))

        # ending delimiters
        if c == b')':
            raise PDFSyntaxError("close parenthesis outside a string")
        if c == b']':
            return _array_end
        if c == b'}':
            return _carray_end

        if c == b'>':
            c = next(p)
            if c == b'>':
                return _dict_end
            else:
                raise PDFSyntaxError("'>' outside a hex string")

        # "a sequence of consecutive regular characters comprises a
        # single token"
        p.pushback(c)
        rv = self.parse_regular_token()

        # check for numbers
        if _number_r.match(rv):
            if b'.' not in rv: return int(rv)
            else: return float(rv)

        # convert to operator, check for inline image
        # note: the #xx notation is *not* processed for operators
        rv = Operator(rv)
        if rv is _image_begin:
            return parse_inline_image(rv)
        return rv

    def skip_whitespace_and_comments(self):
        # note: StopIteration here is deliberately allowed to propagate to
        # the caller of next().
        p = self._data
        while True:
            c = next(p)
            if c not in b' \t\r\n\f':
                if c != b'%':
                    p.pushback(c)
                    return
                # comments run to end of line
                while c not in b'\r\n':
                    c = next(p)

    def parse_regular_token(self):
        p = self._data
        c = next(p)
        tk = []
        try:
            while c not in b' \t\r\n\f()<>[]{}/%':
                tk.append(c)
                c = next(p)
            p.pushback(c)
        except StopIteration:
            pass # EOF ends token
        return b''.join(tk)

    def parse_name_literal(self):
        rv = self.parse_regular_token()
        if rv == b'': raise PDFSyntaxError("slash not followed by a name")
        return Name(_unescape_id(rv))

    def parse_string(self):
        p = self._data
        text = []
        lparens = 1
        try:
            while True:
                c = next(p)

                if c == b'(':
                    lparens += 1
                elif c == b')':
                    lparens -= 1
                    if lparens == 0: break
                elif c == b'\r':
                    # \r\n gets converted to \n if not preceded by a backslash.
                    c = next(p)
                    if c != b'\n':
                        p.pushback(c)
                        c = b'\n'
                elif c == b'\\':
                    c = next(p)
                    if   c == b'n': c = b'\n'
                    elif c == b'r': c = b'\r'
                    elif c == b't': c = b'\t'
                    elif c == b'b': c = b'\b'
                    elif c == b'f': c = b'\f'
                    elif c in b'01234567': # octal escape
                        n = ord(c) - ord('0')
                        c = next(p)
                        if c in b'01234567':
                            n = n * 8 + (ord(c) - ord('0'))
                            c = next(p)
                            if c in b'01234567':
                                n = n * 8 + (ord(c) - ord('0'))
                                c = next(p)
                        p.pushback(c)
                        c = chr(n)
                    elif c == b'\n':
                        continue # backslash-newline is eaten
                    elif c == b'\r':
                        c = next(p)
                        if c != b'\n': p.pushback(c)
                        continue
                    else:
                        # ??? The PDF Reference says \(, \), and \\ stand
                        # for (, ), and \ respectively, but also says the
                        # \ is "ignored" if the character that follows is
                        # not one of the above set.  For now we assume that
                        # means \<anything> maps to <anything> if not in the
                        # above clauses.
                        pass

                text.append(c)

        except StopIteration:
            raise PDFSyntaxError("EOF inside a string")
        return b''.join(text)

    def parse_hex_string(self, first):
        pass

    def parse_array(self, isbraced):
        if isbraced: rv = CArray()
        else: rv = Array()
        try:
            while True:
                item = next(self)
                if item == _array_end:
                    if isbraced:
                        raise PDFSyntaxError("[-array ended by }")
                    return rv
                elif item == _carray_end:
                    if not isbraced:
                        raise PDFSyntaxError("{-array ended by ]")
                    return rv

                elif item == _dict_end:
                    raise PDFSyntaxError("unbalanced dictionary close operator")
                elif (item == _image_begin or 
                      item == _image_end or
                      item == _image_data):
                    raise PDFSyntaxError("stray inline image operator")
                else:
                    rv.push(item)

        except StopIteration:
            raise PDFSyntaxError("EOF inside an array")

    def parse_dict(self, isimage):
        if isimage: rv = IIDict()
        else: rv = Dict()
        try:
            while True:
                key = next(self)
                if key == _dict_end:
                    if isimage:
                        raise PDFSyntaxError("image dict ended by '>>'")
                    return rv
                if key == _image_data:
                    if not isimage:
                        raise PDFSyntaxError("dict ended by 'ID'")
                    return rv

                if not isinstance(key, Name):
                    raise PDFSyntaxError("dictionary key is not a name")
                if key in rv:
                    raise PDFSyntaxError("duplicate dictionary key " + key)

                value = next(self)
                if value == _dict_end or value == _image_data:
                    raise PDFSyntaxError("dictionary key with no value")

                if value == _array_end or value == _carray_end:
                    raise PDFSyntaxError("unbalanced array close operator")
                if value == _image_begin or value == _image_end:
                    raise PDFSyntaxError("stray inline image operator")

                # "Specifying the null object as the value of a dictionary
                # entry shall be equivalent to omitting the entry entirely."
                if value is not None:
                    rv[key] = value

        except StopIteration:
            raise PDFSyntaxError("EOF inside a dictionary")

    def parse_inline_image(self):
        pass
