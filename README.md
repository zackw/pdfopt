# PDFOpt - A PDF Content-Stream Optimizer

This is the beginnings of a library to optimize PDF content streams.
A "content stream" is the PDF term-of-art for a packaged sequence of
drawing instructions; for instance, there is normally one content
stream for each page in a PDF file.  Many programs that generate PDFs
do not take any care at all over the efficiency of their drawing
operations, leading to documents that are much larger than they need
to be, slower to render, and can cause renderers (especially actual
printers, alas) to choke.

I say "beginnings" because the actual optimizer has not yet been
written; I began this project in 2010 and almost immediately ran out
of time to work on it.  All that there is right now is an incomplete
*parser* for content streams.  Still, it could be useful as is.  If
you have an immediate need to make a PDF document more compact or
efficient, modern versions of [Ghostscript](http://ghostscript.com/)
include a page optimizer:

    $ gs -q -dBATCH -dNOPAUSE -dSAFER -sDEVICE=pdfwrite \
         -dPDFSETTINGS=/printer -sOutputFile=out.pdf in.pdf

will probably do what you want.

All the present code is in Python, but the long-term intent is to
write the optimizer in C or C++ so that it can be incorporated into
[QPDF](https://github.com/qpdf/qpdf), keeping a Python version around
for reference.  This is the reason for the unusual choice of license.
It would also be nice to include an optimizer in common PDF *creation*
libraries, eliminating the original problem at source, and so I will
consider most any request for license adjustments necessary to
incorporate this code into some other work of free software.
