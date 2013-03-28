# Copyright 2010-2013 Zack Weinberg <zackw@panix.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the Artistic License 2.0.  See the file
# "Artistic-2.0" in the source distribution, or
# <http://www.opensource.org/licenses/artistic-license-2.0.php>, for
# further details.

# Test suite for pdfcontent.

import pdfcontent
import unittest

import itertools
import sys
import random

rng = random.Random()

class t_PDFSyntaxError(unittest.TestCase):
    def test_catch_exact(self):
        try:
            raise pdfcontent.PDFSyntaxError()
        except pdfcontent.PDFSyntaxError:
            return
        except:
            self.fail("caught some other kind of exception: " + sys.exc_info())
        else:
            self.fail("didn't catch an exception")

    def test_catch_fuzzy(self):
        try:
            raise pdfcontent.PDFSyntaxError()
        except Exception:
            return
        except:
            self.fail("didn't catch a PDFSyntaxError as an Exception")
        else:
            self.fail("didn't catch an exception")

class t_PushbackIterator(unittest.TestCase):
    def test_straightthrough(self):
        pbi = pdfcontent.PushbackIterator((1,2,3,4,5))
        self.assertEqual(next(pbi), 1)
        self.assertEqual(next(pbi), 2)
        self.assertEqual(next(pbi), 3)
        self.assertEqual(next(pbi), 4)
        self.assertEqual(next(pbi), 5)
        self.assertRaises(StopIteration, next, pbi)

    def test_pushingback(self):
        pbi = pdfcontent.PushbackIterator((1,2,3,4,5))
        self.assertEqual(next(pbi), 1)
        pbi.pushback(100)
        self.assertEqual(next(pbi), 100)
        self.assertEqual(next(pbi), 2)
        pbi.pushback(101)
        pbi.pushback(102)
        self.assertEqual(next(pbi), 102)
        self.assertEqual(next(pbi), 101)
        self.assertEqual(next(pbi), 3)
        pbi.pushback(103)
        pbi.pushback(104)
        pbi.pushback(105)
        self.assertEqual(next(pbi), 105)
        self.assertEqual(next(pbi), 104)
        self.assertEqual(next(pbi), 103)
        self.assertEqual(next(pbi), 4)
        pbi.pushback(106)
        pbi.pushback(107)
        pbi.pushback(108)
        pbi.pushback(109)
        self.assertEqual(next(pbi), 109)
        self.assertEqual(next(pbi), 108)
        self.assertEqual(next(pbi), 107)
        self.assertEqual(next(pbi), 106)
        self.assertEqual(next(pbi), 5)
        pbi.pushback(110)
        pbi.pushback(111)
        pbi.pushback(112)
        pbi.pushback(113)
        pbi.pushback(114)
        self.assertEqual(next(pbi), 114)
        self.assertEqual(next(pbi), 113)
        self.assertEqual(next(pbi), 112)
        self.assertEqual(next(pbi), 111)
        self.assertEqual(next(pbi), 110)
        self.assertRaises(StopIteration, next, pbi)

class t_ftod(unittest.TestCase):
    def test_invalid(self):
        ftod = pdfcontent.ftod
        cases = [ "", "$", "dog", "e23", ".", "-", "-.", "+", "+1.2",
                  "0x1.24p2", "3.0f", "3.40282346638528860e+38l" ]
        for c in cases:
            with self.assertRaises(RuntimeError) as err:
                ftod(c)
            self.assertRegex(str(err.exception),
                             r"^unexpected floating point number format: b'.*'$")

    def test_zeroes(self):
        ftod = pdfcontent.ftod
        cases = [ "0", "-0", "-0.0", "0000000", "-000000.0000000",
                  "0e+42", "0e-42", "0.0e+42" ]
        for c in cases:
            self.assertEqual(ftod(c), b'0')

    def test_exponent(self):
        ftod = pdfcontent.ftod
        cases = { "1e+0" : b'1',
                  "1e+1" : b'10',
                  "1e+2" : b'100',
                  "1e+4" : b'10000',
                  "1e-1" : b'.1',
                  "1e-2" : b'.01',
                  "1e-4" : b'.0001',
                  "271.828e-4" : b'.0271828',
                  "271.828e-3" : b'.271828',
                  "271.828e-2" : b'2.71828',
                  "271.828e-1" : b'27.1828',
                  "271.828e+0" : b'271.828',
                  "271.828e+1" : b'2718.28',
                  "271.828e+2" : b'27182.8',
                  "271.828e+3" : b'271828',
                  "271.828e+4" : b'2718280',
                  6.02e23 : b'602000000000000000000000',
                  60.2e22 : b'602000000000000000000000',
                  .602e24 : b'602000000000000000000000',
                  6.62e-34 : b'.000000000000000000000000000000000662',
                  66.2e-35 : b'.000000000000000000000000000000000662',
                  662e-36  : b'.000000000000000000000000000000000662',
        }
        for inp, out in cases.items():
            self.assertEqual(ftod(inp), out)
            if isinstance(inp, float):
                self.assertEqual(ftod(-inp), b'-'+out)
            else:
                self.assertEqual(ftod("-"+inp), b'-'+out)

    def test_many_integers(self):
        ftod = pdfcontent.ftod
        for i in range(10000):
            n = rng.randint(-2**32, 2**32-1)
            expected = bytes(str(n), "us-ascii")
            self.assertEqual(ftod(n), expected)
            self.assertEqual(ftod(float(n)), expected)
            self.assertEqual(ftod(str(n) + ".00000"), expected)
            if n >= 0:
                self.assertEqual(ftod("0000" + str(n)), expected)
            else:
                self.assertEqual(ftod("-0000" + str(-n)), expected)

    def test_many_floats(self):
        ftod = pdfcontent.ftod
        for i in range(10000):
            n = rng.uniform(1e-4, 1e+16)
            s = str(n)
            if s.startswith("0."): s = s[1:]
            elif s.endswith(".0"): s = s[:-2]
            self.assertEqual(ftod(n), bytes(s, "us-ascii"))

class t_gen_paren_string(unittest.TestCase):
    def test_simple_strings(self):
        gps = pdfcontent.gen_paren_string
        cases = { b'abc': b'(abc)',
                  b'\\':  b'(\\\\)',
                  b'\n':  b'(\n)',
                  bytes(range(0,256)) :
          b'(\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
           b'\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'
           b'\x20\x21\x22\x23\x24\x25\x26\x27\x28\x29\x2a\x2b\x2c\x2d\x2e\x2f'
           b'\x30\x31\x32\x33\x34\x35\x36\x37\x38\x39\x3a\x3b\x3c\x3d\x3e\x3f'
           b'\x40\x41\x42\x43\x44\x45\x46\x47\x48\x49\x4a\x4b\x4c\x4d\x4e\x4f'
           b'\x50\x51\x52\x53\x54\x55\x56\x57\x58\x59\x5a\x5b\\\\\x5d\x5e\x5f'
           b'\x60\x61\x62\x63\x64\x65\x66\x67\x68\x69\x6a\x6b\x6c\x6d\x6e\x6f'
           b'\x70\x71\x72\x73\x74\x75\x76\x77\x78\x79\x7a\x7b\x7c\x7d\x7e\x7f'
           b'\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f'
           b'\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f'
           b'\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf'
           b'\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf'
           b'\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf'
           b'\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf'
           b'\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef'
           b'\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff)'
        }
        for inp, out in cases.items():
            self.assertEqual(gps(inp), out)

    def test_paren_matching(self):
        pass

class t_idescape(unittest.TestCase):
    def test_id_escape(self):
        inp = bytes(range(0,256))
        out = (b'#00#01#02#03#04#05#06#07#08#09#0A#0B#0C#0D#0E#0F'
               b'#10#11#12#13#14#15#16#17#18#19#1A#1B#1C#1D#1E#1F'
               b'#20!"#23$#25&\'#28#29*+,-.#2F0123456789:;#3C=#3E?'
               b'@ABCDEFGHIJKLMNOPQRSTUVWXYZ#5B\\#5D^_'
               b'`abcdefghijklmnopqrstuvwxyz#7B|#7D~#7F'
               b'#80#81#82#83#84#85#86#87#88#89#8A#8B#8C#8D#8E#8F'
               b'#90#91#92#93#94#95#96#97#98#99#9A#9B#9C#9D#9E#9F'
               b'#A0#A1#A2#A3#A4#A5#A6#A7#A8#A9#AA#AB#AC#AD#AE#AF'
               b'#B0#B1#B2#B3#B4#B5#B6#B7#B8#B9#BA#BB#BC#BD#BE#BF'
               b'#C0#C1#C2#C3#C4#C5#C6#C7#C8#C9#CA#CB#CC#CD#CE#CF'
               b'#D0#D1#D2#D3#D4#D5#D6#D7#D8#D9#DA#DB#DC#DD#DE#DF'
               b'#E0#E1#E2#E3#E4#E5#E6#E7#E8#E9#EA#EB#EC#ED#EE#EF'
               b'#F0#F1#F2#F3#F4#F5#F6#F7#F8#F9#FA#FB#FC#FD#FE#FF')
        self.assertEqual(pdfcontent._escape_id(inp), out)

    def test_id_unescape(self):
        chars = [chr(x) for x in range(0,256)]
        escapes = ["#{:02X}".format(x) for x in range(0,256)]
        regulars = ('!"$&\'*+-.0123456789:;=?'
                    '@ABCDEFGHIJKLMNOPQRSTUVWXYZ\\^_'
                    '`abcdefghijklmnopqrstuvwxyz|~')
        for r in regulars:
            inp = bytes(r.join(escapes), "latin-1")
            out = bytes(r.join(chars), "latin-1")
            self.assertEqual(pdfcontent._unescape_id(inp), out)

class t_OpName(unittest.TestCase):
    def test_printing(self):
        self.assertEqual(pdfcontent.Operator(b'abc').serialize(), b'abc')
        self.assertEqual(pdfcontent.Operator(b'{}').serialize(), b'#7B#7D')
        self.assertEqual(pdfcontent.Name(b'abc').serialize(), b'/abc')
        self.assertEqual(pdfcontent.Name(b'{}').serialize(), b'/#7B#7D')

    def test_intern(self):
        oa = pdfcontent.Operator(b'a')
        ob = pdfcontent.Operator(b'b')
        na = pdfcontent.Name(b'a')
        nb = pdfcontent.Name(b'b')
        self.assertIs(oa, pdfcontent.Operator(b'a'))
        self.assertIs(ob, pdfcontent.Operator(b'b'))
        self.assertIs(na, pdfcontent.Name(b'a'))
        self.assertIs(nb, pdfcontent.Name(b'b'))
        self.assertIsNot(oa, na)
        self.assertIsNot(ob, nb)

if __name__ == '__main__':
    unittest.main()
