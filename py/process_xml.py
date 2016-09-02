#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Copyright (c) 2016 the authors of the https://github.com/publicdocs project.
# Use of this file is subject to the NOTICE file in the root of the repository.
#

# OVERVIEW:
# We want to take the XML version of the US Code, as published by the Office of the
# Law Revision Counsel, convert it into a format that can be easily viewed in a
# Git repository, and view how it changes over time as Git revision history.
# Due to the limitations of most Git visualization software, this requires breaking up
# the Code into multiple text-like files.
#
# For the original downloads see, see: http://uscode.house.gov/download/download.shtml
#
# As of 2016-Aug-29, http://uscode.house.gov/robots.txt doesn't disallow all bots,
# but, regardless, we want to be courteous and be sure not to overload their servers.
#
# Store the hash of the ZIP file. This is especially important since we couldn't
# find an HTTPS download for these files =(
#

import urllib2
import urllib
import hashlib
import os
import codecs
import zlib
import argparse
import shutil
import StringIO
import zipfile


from xml.etree import ElementTree
from string import Template
from collections import namedtuple
from multiprocessing import Pool

## CONSTANTS

_out_header_markdown = Template(u"""# $fancytitle, USLM ref $filepart

* Portions Copyright © 2016 the authors of the https://github.com/publicdocs project.
  Use of this file is subject to the NOTICE at [https://github.com/publicdocs/uscode/blob/master/NOTICE](https://github.com/publicdocs/uscode/blob/master/NOTICE)
* See the [Document Metadata](${docmd}) for more information.
  This file is generated from historical government data; content and/or formatting may be inaccurate and out-of-date and should not be used for official purposes.

----------
----------

$navlinks

$innercontent

----------

$navlinks

----------
----------

$linkset

""")


_out_readme_markdown = Template(u"""# $fancytitle (Release Point PL ${rp1}-${rp2})

* Portions Copyright © 2016 the authors of the https://github.com/publicdocs project.
  Use of this file is subject to the NOTICE at [https://github.com/publicdocs/uscode/blob/master/NOTICE](https://github.com/publicdocs/uscode/blob/master/NOTICE)
* See the [Document Metadata](#document-metadata) below for more information.
  This file is generated from historical government data; content and/or formatting may be inaccurate and out-of-date and should not be used for official purposes.

----------

## Document Metadata

This is a modified, processed, and marked-up version of the US Code,
generated by the https://github.com/publicdocs project.

* Original provenance
    * URL: $url
    * SHA 512 digest = $sha512zip
    * Release Point: ${rp1}-${rp2}
* Title $title
    * XML File: $titlefile
    * SHA 512 digest = $sha512xml

For more information on the original source, see:
http://uscode.house.gov/download/download.shtml

$issues

XML file metadata:

```
$origmd
```

## Important Notice

```
$notice
```


----------

## Contents

$index

""")

_download_url_template = Template('http://uscode.house.gov/download/releasepoints/us/pl/$rp1/$rp2/xml_uscAll@$rp1-$rp2.zip')

NBSP = u"\u00A0"

_sp = "{http://xml.house.gov/schemas/uslm/1.0}"
TAG_META = _sp + "meta"

TAG_APPENDIX = _sp + "appendix"
TAG_COURT_RULES = _sp + "courtRules"
TAG_COMPILED_ACT = _sp + "compiledAct"
TAG_TITLE = _sp + "title"
TAG_SUBTITLE = _sp + "subtitle"
TAG_CHAPTER = _sp + "chapter"
TAG_SUBCHAPTER = _sp + "subchapter"
TAG_PART = _sp + "part"
TAG_SUBPART = _sp + "subpart"
TAG_DIVISION = _sp + "division"
TAG_SUBDIVISION = _sp + "subdivision"
TAG_ARTICLE = _sp + "article"
TAG_SUBARTICLE = _sp + "subarticle"

TAG_SECTION = _sp + "section"
TAG_COURT_RULE = _sp + "courtRule"

TAGS_SECTION_LIKE = [TAG_SECTION, TAG_COURT_RULE]

TAGS_LARGE = [TAG_APPENDIX, TAG_COMPILED_ACT, TAG_COURT_RULES, TAG_TITLE, TAG_SUBTITLE, TAG_CHAPTER, TAG_SUBCHAPTER, TAG_PART, TAG_SUBPART, TAG_DIVISION, TAG_SUBDIVISION, TAG_ARTICLE, TAG_SUBARTICLE]

TAGS_HEADINGS = []

TAGS_HEADINGS.extend(TAGS_LARGE)
TAGS_HEADINGS.extend(TAGS_SECTION_LIKE)

TAG_SUBSECTION = _sp + "subsection"
TAG_PARAGRAPH = _sp + "paragraph"
TAG_SUBPARAGRAPH = _sp + "subparagraph"
TAG_CLAUSE = _sp + "clause"
TAG_SUBCLAUSE = _sp + "subclause"
TAG_ITEM = _sp + "item"
TAG_SUBITEM = _sp + "subitem"
TAG_SUBSUBITEM = _sp + "subsubitem"

TAGS_SMALL = [TAG_SUBSECTION, TAG_PARAGRAPH, TAG_SUBPARAGRAPH, TAG_CLAUSE, TAG_SUBCLAUSE, TAG_ITEM, TAG_SUBITEM, TAG_SUBSUBITEM]

TAG_HEADING = _sp + "heading"
TAGS_BOLDEN = [TAG_HEADING]

TAG_CHAPEAU = _sp + "chapeau"
TAG_CONTENT = _sp + "content"
TAG_CONTINUATION = _sp + "continuation"

_shtml = "{http://www.w3.org/1999/xhtml}"

TAG_P = _shtml + "p"

TAG_QUOTEDCONTENT = _sp + "quotedContent"
TAGS_QUOTED = [TAG_QUOTEDCONTENT]

TAGS_BREAK = [TAG_CHAPEAU, TAG_CONTINUATION, TAG_P]
TAGS_BREAK.extend(TAGS_HEADINGS)
TAGS_BREAK.extend(TAGS_SMALL)

TAG_NOTE = _sp + "note"
TAG_REF = _sp + "ref"

TAG_LAYOUT = _sp + "layout"
TAG_HEADER = _sp + "header"
TAG_TOC_ITEM = _sp + "tocItem"
TAG_COLUMN = _sp + "column"

TAG_TABLE = _shtml + "table"
TAG_TR = _shtml + "tr"
TAG_TD = _shtml + "td"
TAG_TH = _shtml + "th"
TAG_THEAD = _shtml + "thead"
TAG_TBODY = _shtml + "tbody"
TAG_TFOOT = _shtml + "tfoot"
TAG_COLGROUP = _shtml + "colgroup"

## STRUCTURES
ZipContents = namedtuple("ZipContents", "sha512 titledir")
ProcessedElement = namedtuple("ProcessedElement", "inputmeta outputmd tail")
FileDelimiter = namedtuple("FileDelimiter", "identifier dir titleroot reporoot prev next filename")
FileDelimiter.__new__.__defaults__ = (None, ) * len(FileDelimiter._fields)
Link = namedtuple("Link", "refcontent href")

## FUNCTIONS

# A release point is labeled like Public Law 114-195, i.e. Public Law rp1-rp2
def download(rp1, rp2):
    # TODO, for now just manually download the file
    return 0


def md_header_prefix(identifier):
    # An identifier of /us/usc/t1/s1 gets two chars: ==
    # and we never have more than 6 chars
    c = unicode(identifier).count(u'/') - 2
    if c > 6:
        c = 6
    return (u"#" * c) + u" "

# No links, images, or html tags. Don't auto bold or italics either
_md_escape_chars = list(u'\\`_{}[]<>*_')
def md_escape(txt):
    ret = u""
    for c in txt:
        if c in _md_escape_chars:
            ret = ret + "\\"
        ret = ret + c
    return ret

def md_indent(clazz):
    ind = 0
    if u"indent13" in clazz:
        ind = 14
    elif u"indent12" in clazz:
        ind = 13
    elif u"indent11" in clazz:
        ind = 12
    elif u"indent10" in clazz:
        ind = 11
    elif u"indent9" in clazz:
        ind = 10
    elif u"indent8" in clazz:
        ind = 9
    elif u"indent7" in clazz:
        ind = 8
    elif u"indent6" in clazz:
        ind = 7
    elif u"indent5" in clazz:
        ind = 6
    elif u"indent4" in clazz:
        ind = 5
    elif u"indent3" in clazz:
        ind = 4
    elif u"indent2" in clazz:
        ind = 3
    elif u"indent1" in clazz:
        ind = 2
    elif u"indent0" in clazz:
        ind = 1
    if ind > 0:
        return NBSP * 2
    return u''


def process_zip(input_zip, wd):
    wdir = wd + '/unzipped'
    if os.path.exists(wdir):
        shutil.rmtree(wdir)
    os.makedirs(wdir)
    hasher = hashlib.sha512()
    try:
        hasher.update(input_zip.read())
        input_zip.seek(0)
        zip = zipfile.ZipFile(input_zip, 'r')
        zip.extractall(wdir)
    finally:
        input_zip.close()
    sha = hasher.hexdigest()
    return ZipContents(sha512 = sha, titledir = wdir)

def prep_output(wd):
    wdir = wd + '/gen'
    if os.path.exists(wdir):
        shutil.rmtree(wdir)
    os.makedirs(wdir)

def has_class(elem, clazz):
    g = elem.get("class")
    if not g:
        return False
    if g == clazz:
        return True
    return g.endswith(u" " + clazz) or g.startswith(clazz + u" ")

def process_element(elem, nofmt = False):
    meta = u''
    tag = elem.tag
    text = elem.text
    attrib = elem.attrib
    tail = elem.tail
    # Rule: Any text content must be MD-escaped
    outputs = []
    links = []
    footnotes = []
    filesep = None
    cid = None
    content_pre = u''
    content_post = u''
    line_content_pre = u''
    line_content_post = u''
    chnofmt = False
    extraproc = False

    # Example of a footnote in context:
    # title 15,<ref class="footnoteRef" idref="fn002021">1</ref><note type="footnote" id="fn002021"><num>1</num> See References in Text note below.</note> the ter
    if tag == TAG_REF and has_class(elem, u"footnoteRef"):
        outputs.append(u' <sup>\[')
    elif tag == TAG_REF and elem.get('href'):
        outputs.append(u'[')

    if tag == TAG_NOTE and u"footnote" == elem.get(u'type'):
        outputs.append(u' <sup> ')

    if tag == TAG_META:
        meta = unicode(ElementTree.tostring(elem))
    #elif tag == TAG_REF:
    #    ref = '#'
    #    outputs.append(u'[' + u''.join(elem.itertext()) + '](' + ref + ')')
    elif tag == TAG_LAYOUT:
        outputs.append(u'\n\n<table>\n')
        for rowe in elem:
            if not (rowe.tag == TAG_HEADER or rowe.tag == TAG_TOC_ITEM):
                print u"(FATAL) #### FAIL layout FOUND ROW " + rowe.tag
                assert(False)
                system.exit(3)
                return None
            if rowe.get(u'rowspan'):
                outputs.append(u'  <tr rowspan="' + str(int(rowe.get(u'rowspan')))+ '">\n')
            else:
                outputs.append(u'  <tr>\n')
            for cole in rowe:
                if not (cole.tag == TAG_COLUMN):
                    print u"(FATAL) #### FAIL layout FOUND COL " + cole.tag
                    assert(False)
                    system.exit(3)
                    return None
                if cole.get(u'colspan'):
                    outputs.append(u'    <td colspan="' + str(int(cole.get(u'colspan')))+ '"> ')
                else:
                    outputs.append(u'    <td> ')
                colouts = []
                p = process_element(cole, chnofmt)
                if p.outputmd:
                    # Already escaped
                    for txtp in p.outputmd:
                        if not txtp:
                            continue
                        if isinstance(txtp, FileDelimiter):
                            continue
                        colouts.append(txtp)
                outputs.extend(colouts)
                outputs.append(u'  </td>\n')
            outputs.append(u'\n  </tr>\n')
        outputs.append(u'</table>\n')
    elif tag == TAG_TABLE:
        outputs.append(u'\n\n<table>\n')
        for sect in elem:
            if sect.tag == TAG_COLGROUP:
                continue
            elif sect.tag == TAG_THEAD or sect.tag == TAG_TBODY or sect.tag == TAG_TFOOT:
                for rowe in sect:
                    if not (rowe.tag == TAG_TR):
                        print u"(FATAL) #### FAIL table FOUND ROW " + rowe.tag
                        assert(False)
                        system.exit(3)
                        return None
                    if rowe.get(u'rowspan'):
                        outputs.append(u'  <tr rowspan="' + str(int(rowe.get(u'rowspan')))+ '">\n')
                    else:
                        outputs.append(u'  <tr>\n')
                    for cole in rowe:
                        if not (cole.tag == TAG_TD or cole.tag == TAG_TH):
                            print u"(FATAL) #### FAIL table FOUND COL " + cole.tag
                            assert(False)
                            system.exit(3)
                            return None
                        if cole.get(u'colspan'):
                            outputs.append(u'    <td colspan="' + str(int(cole.get(u'colspan')))+ '"> ')
                        else:
                            outputs.append(u'    <td> ')
                        colouts = []
                        p = process_element(cole, chnofmt)
                        if p.outputmd:
                            # Already escaped
                            for txtp in p.outputmd:
                                if not txtp:
                                    continue
                                if isinstance(txtp, FileDelimiter):
                                    continue
                                colouts.append(txtp)
                        outputs.extend(colouts)
                        outputs.append(u'  </td>\n')
                    outputs.append(u'\n  </tr>\n')
            else:
                rowe = sect
                if not (rowe.tag == TAG_TR):
                    print u"(FATAL) #### FAIL table FOUND ROW " + rowe.tag
                    assert(False)
                    system.exit(3)
                    return None
                if rowe.get(u'rowspan'):
                    outputs.append(u'  <tr rowspan="' + str(int(rowe.get(u'rowspan')))+ '">\n')
                else:
                    outputs.append(u'  <tr>\n')
                for cole in rowe:
                    if not (cole.tag == TAG_TD or cole.tag == TAG_TH):
                        print u"(FATAL) #### FAIL table FOUND COL " + cole.tag
                        assert(False)
                        system.exit(3)
                        return None
                    if cole.get(u'colspan'):
                        outputs.append(u'    <td colspan="' + str(int(cole.get(u'colspan')))+ '"> ')
                    else:
                        outputs.append(u'    <td> ')
                    colouts = []
                    p = process_element(cole, chnofmt)
                    if p.outputmd:
                        # Already escaped
                        for txtp in p.outputmd:
                            if not txtp:
                                continue
                            if isinstance(txtp, FileDelimiter):
                                continue
                            colouts.append(txtp)
                    outputs.extend(colouts)
                    outputs.append(u'  </td>\n')
                outputs.append(u'\n  </tr>\n')
        outputs.append(u'</table>\n')
    else:
        extraproc = True
        if elem.get('identifier') and (tag in TAGS_HEADINGS):
            cid = elem.get('identifier')
            filesep = unicode(cid)
            chnofmt = True
            outputs.append(u'\n\n' + md_header_prefix(cid))
        elif tag in TAGS_BREAK:
            outputs.append(u'\n\n')
        elif tag in TAGS_BOLDEN:
            if not nofmt:
                content_pre = u' __'
                content_post = u'__ '
        elif tag in TAGS_QUOTED:
            if True or not nofmt:
                line_content_pre = u'\n> '
                line_content_post = u' '

        if text:
            if text.strip() and (content_pre or content_post):
                outputs.append(content_pre + md_escape(unicode(text).strip()) + content_post)
            else:
                outputs.append(md_escape(unicode(text)))

        for child in elem:
            p = process_element(child, chnofmt)
            if p.outputmd:
                # Already escaped
                for txtp in p.outputmd:
                    if not txtp:
                        continue
                    if isinstance(txtp, FileDelimiter) or isinstance(txtp, Link):
                        outputs.append(txtp)
                        continue
                    if txtp.strip() and (content_pre or content_post):
                        outputs.append(content_pre + txtp + content_post)
                    else:
                        outputs.append(txtp)
            if p.inputmeta:
                meta = meta + p.inputmeta
            if p.tail:
                if p.tail.strip() and (content_pre or content_post):
                    outputs.append(content_pre + md_escape(unicode(p.tail).strip()) + content_post)
                else:
                    outputs.append(md_escape(unicode(p.tail)))

    if tag == TAG_HEADING:
        outputs.append(u'\n')

    if tag == TAG_REF and has_class(elem, u"footnoteRef"):
        outputs.append(u'\]</sup> ')
    elif tag == TAG_REF and elem.get(u'href'):
        href = md_escape(elem.get(u'href'))
        outputs.append(u'][' + href + u']')
        outputs.append(Link(href=elem.get(u'href'), refcontent=href))

    if tag == TAG_NOTE and u"footnote" == elem.get(u'type'):
        outputs.append(u' </sup> ')

    ind = u""
    if extraproc and elem.get('class'):
        ind = md_indent(elem.get('class'))

    outputs2 = []
    lastnl = True
    for o in outputs:
        if isinstance(o, FileDelimiter):
            lastnl = True
            outputs2.append(o)
        elif isinstance(o, Link):
            outputs2.append(o)
        else:
            if extraproc and o.strip() and lastnl:
                outputs2.append(ind + line_content_pre + o)
            else:
                outputs2.append(o)
            lastnl = o.endswith(u'\n')

    if filesep:
        if tag in TAGS_SECTION_LIKE:
            outputs2.insert(0, FileDelimiter(identifier=filesep, dir=None))
        else:
            outputs2.insert(0, FileDelimiter(identifier=filesep, dir=filesep))

    retp = ProcessedElement(inputmeta = meta, outputmd = outputs2, tail = elem.tail)
    return retp

def delete_line(path1, path2, num):
    fr = codecs.open(path1, 'rb', encoding='utf-8')
    fw = codecs.open(path2, 'wb', encoding='utf-8')
    i = 1
    for line in fr:
        if i == num:
            fw.write(u'\n')
        else:
            fw.write(line)
        i = i + 1
    fr.close()
    fw.close()

def replace_line(path1, path2, a1, a2):
    fr = codecs.open(path1, 'rb', encoding='utf-8')
    fw = codecs.open(path2, 'wb', encoding='utf-8')
    i = 1
    for line in fr:
        if line == a1:
            fw.write(a2)
        else:
            fw.write(line)
        i = i + 1
    fr.close()
    fw.close()

def md_fancy(cid):
    return cid


def dir_safe_uslm_id(cid):
    if u":" in cid:
        print u"(FATAL) #### Cannot have ':' in identifier " + cid
        assert(False)
        sys.exit(2)
        return
    if u"*" in cid:
        print u"(FATAL) #### Cannot have '*' in identifier " + cid
        assert(False)
        sys.exit(2)
        return
    if u"$" in cid:
        print u"(FATAL) #### Cannot have '$' in identifier " + cid
        assert(False)
        sys.exit(2)
        return
    if u"@" in cid:
        print u"(FATAL) #### Cannot have '@' in identifier " + cid
        assert(False)
        sys.exit(2)
        return
    if u".." == cid or u"/../" == cid or u"/.." in cid or u"../" in cid:
        print u"(FATAL) #### Cannot have '..' in identifier " + cid
        assert(False)
        sys.exit(2)
        return
    if cid.startswith(u".") or cid.endswith(u"."):
        print u"(FATAL) #### Cannot start or end with '.' in identifier " + cid
        assert(False)
        sys.exit(2)
        return
    return cid

def file_safe_uslm_id(cid):
    cid = cid.replace(u'/', u'_').replace(u':', u'_').replace(u'*', u'_').replace(u'$', u'_')

    if u"/" in cid:
        print u"(FATAL) #### Cannot have '/' in identifier " + cid
        assert(False)
        sys.exit(2)
        return
    if u".." == cid or u"/../" == cid or u"/.." in cid or u"../" in cid:
        print u"(FATAL) #### Cannot have '..' in identifier " + cid
        assert(False)
        sys.exit(2)
        return
    return cid

def process_title(zip_contents, title, rp1, rp2, notice, wd):
    rp1 = unicode(rp1)
    rp2 = unicode(rp2)
    notice = unicode(notice)
    title = unicode(title)
    wdir = wd + u'/gen/titles/usc' + title
    issues = u''
    if os.path.exists(wdir):
        shutil.rmtree(wdir)
    os.makedirs(wdir)
    of = wdir + u'/title.md'
    zipurl = _download_url_template.substitute(rp1 = rp1, rp2 = rp2)
    titlefilename = u"usc" + title + u".xml"
    moredir = "xml/"
    if not (os.path.exists(zip_contents.titledir + u"/" + moredir) and os.path.isdir(zip_contents.titledir + u"/" + moredir)):
        moredir = u""
    titlepath = zip_contents.titledir + u"/" + moredir + titlefilename


    hasher = hashlib.sha512()
    try:
        hasher.update(open(titlepath, 'rb').read())
    except:
        print u"(Non-Fatal) #### Skipping; Could not read title " + str(title)
        return -1
    xmlsha = hasher.hexdigest()

    if rp1 == u"113" and rp2 == u"46" and title == u"16":
        print u"(FATAL) #### usc16.xml at release 113-46 is a corrupt file"
        assert(False)
        sys.exit(2)
        return
    if rp1 == u"113" and rp2 == u"65" and title == u"31":
        print u"(FATAL) #### usc31.xml at release 113-65 is a corrupt file"
        assert(False)
        sys.exit(2)
        return
    if rp1 == u"114":
        if rp2 in [u"93not92", u"100not94not95", u"114not95not113", u"115not95"]:
            if title == u"50A":
                # thru 114-115, this appendix is borked, missing a </appendix> before a </uscDoc>
                replace_line(titlepath, titlepath + u"_mod.xml", u"</uscDoc>\n", u"</appendix></uscDoc>\n")
                titlepath = titlepath + u"_mod.xml"
                replace_line(titlepath, titlepath + u"_mod.xml", u"</uscDoc>\r", u"</appendix></uscDoc>\r")
                titlepath = titlepath + u"_mod.xml"
                replace_line(titlepath, titlepath + u"_mod.xml", u"</uscDoc>", u"</appendix></uscDoc>")
                titlepath = titlepath + u"_mod.xml"
                iss1 = u"* The XML file is missing a closing \\</appendix\\> before a closing \\</uscDoc\\>; we have inserted the former to process this file.\n"
                print u"(Non-Fatal) #### " +u"ISSUE WITH " + titlepath + u": " + iss1
                issues = issues + iss1


    try:
        origxml = ElementTree.parse(titlepath).getroot()
    except:
        print u"(FATAL) #### FAILURE TO PARSE " + titlepath
        raise



    p = process_element(origxml)
    outsets = []
    fd = None
    lastdir = None
    lastoutset = []
    lastlinkset = []

    titletrunc = title
    while titletrunc.startswith(u'0'):
        titletrunc = titletrunc[1:]

    inc = 0
    allcids = set()
    allfullcids = set()
    osss = p.outputmd
    hasFd = False
    for o in osss:
        if isinstance(o, FileDelimiter):
            hasFd = True
            if o.identifier in allcids:
                print "(Non-Fatal) #### Duplicate USLM identifier " + o.identifier + " at " + titlepath
            allcids.add(o.identifier)
    if not hasFd:
        cid2 = (u"/us/usc/t" + titletrunc).lower()
        print u"(Non-Fatal) #### " + titlepath + u" is missing any file delimiters; adding an artificial one with id =" + cid2
        osss.append(FileDelimiter(identifier=cid2, dir=cid2))


    # dummy terminator
    osss.append(FileDelimiter())
    for o in osss:
        if isinstance(o, FileDelimiter):
            if fd:
                cid = file_safe_uslm_id(fd.identifier)
                fn = (u'/m_') + cid + u'.md'
                tr = u'./' + (u'../' * lastdir.count(u'/'))
                while (lastdir + u'/' + fn) in allfullcids:
                    print "(Non-Fatal) #### Duplicate USLM identifier-file " + lastdir + u'/' + fn + " at " + titlepath
                    cid = file_safe_uslm_id(cid + u'^extra')
                    fn = (u'/m_') + cid + u'.md'
                allfullcids.add(lastdir + u'/' + fn)
                outsets.append([fd._replace(titleroot = tr, dir=lastdir, filename = fn), lastoutset, lastlinkset])
                lastoutset = []
                lastlinkset = []
                inc = inc + 1
            fd = o
            if o.dir:
                lastdir = dir_safe_uslm_id(o.dir)
        else:
            if isinstance(o, Link):
                lastlinkset.append(o)
            else:
                lastoutset.append(o)

    outsets2 = []
    ll = len(outsets)
    for idx, o in enumerate(outsets):
        fd = o[0]
        lo = o[1]
        linkset = o[2]
        lprev = None
        lnext = None
        if idx > 0:
            lp = outsets[idx - 1][0]
            lprev = fd.titleroot + lp.dir + lp.filename
        if idx < ll - 1:
            ln = outsets[idx + 1][0]
            lnext = fd.titleroot + ln.dir + ln.filename
        outsets2.append([fd._replace(prev = lprev, next = lnext), lo, linkset])

    finaloutsets = outsets2

    print "Starting " + str(inc) + " entries for title " + str(title)

    index = u'\n\n'

    isappendix = title.endswith(u'A') or title.endswith(u'a')

    fancytitle = titletrunc + u' U.S.C.'
    if isappendix:
        fancytitle = u"Appendix to " + titletrunc[:-1] + u' U.S.C.'

    for outs in finaloutsets:
        linksetmd = u''
        linkset = outs[2]
        fd = outs[0]
        cid = outs[0].identifier
        cdir = wdir + u'/' + outs[0].dir
        if not os.path.exists(cdir):
            os.makedirs(cdir)
        of = cdir + u'/' + outs[0].filename
        if os.path.exists(of):
            print "(FATAL) #### Cannot have the same identifier multiple times in one directory."
            print "        #### Duplicate USLM identifier " + of + " at " + titlepath
            assert(False)
            sys.exit(2)
            return

        filename_for_readme_index = u'./' + outs[0].dir + u'/' + outs[0].filename

        innercontent = StringIO.StringIO()
        innercontent.write(u''.join(outs[1]))
        cont = innercontent.getvalue()
        cont = u'\n\n'.join([line for line in cont.splitlines() if line.strip()])
        idn = fd.dir.count(u'/') - 3
        if not (fd.dir == cid):
            idn = idn + 1
        index = index + (u'  ' * (idn)) +  u'* [' + cid+ u']('+ filename_for_readme_index  +u')\n'
        linkhtml = u''
        if fd.prev:
            linkhtml = linkhtml + u'[Previous](' + fd.prev + u') | '
        else:
            linkhtml = linkhtml + u'~~Previous~~ | '


        if fd.next:
            linkhtml = linkhtml + u'[Next](' + fd.next + u') | '
        else:
            linkhtml = linkhtml + u'~~Next~~ | '

        if fd.titleroot:
            linkhtml = linkhtml + u'[Root of Title](' + fd.titleroot + u')'
        else:
            linkhtml = linkhtml + u'~~Root of Title~~'

        for l in linkset:
            # refcontent md-escaped on construction
            rurl = md_escape(u'https://publicdocs.github.io/url-resolver/go?ns=uslm&' + urllib.urlencode({u'ref' : unicode(l.href).encode('utf-8')}))
            linksetmd = linksetmd + u'[' + l.refcontent + u']: ' + rurl + u'\n'

        fc = _out_header_markdown.substitute(
                rp1 = rp1,
                rp2 = rp2,
                url = zipurl,
                sha512zip = zip_contents.sha512,
                titlefile = titlefilename,
                docmd = u'./' + fd.titleroot + u'/README.md',
                sha512xml = xmlsha,
                filepart = unicode(cid),
                notice = notice,
                origmd = p.inputmeta,
                title = title,
                navlinks = linkhtml,
                linkset = linksetmd,
                innercontent = cont,
                titletrunc = titletrunc,
                filepartfancy = md_fancy(cid),
                fancytitle = fancytitle,
        )
        f = open(of, 'w')
        f.write(fc.encode('utf8'))
        f.close()

    of = wdir + u'/README.md'
    if issues:
        issues = u'Issues: \n\n' + issues + '\n'
    fc = _out_readme_markdown.substitute(
            rp1 = rp1,
            rp2 = rp2,
            url = zipurl,
            sha512zip = zip_contents.sha512,
            titlefile = titlefilename,
            sha512xml = xmlsha,
            notice = notice,
            issues = issues,
            origmd = p.inputmeta,
            title = title,
            index = index,
            titletrunc = titletrunc,
            fancytitle = fancytitle,
    )
    f = open(of, 'w')
    f.write(fc.encode('utf8'))
    f.close()

    print "Finished " + str(inc) + " entries for title " + str(title)


class title_processor:
    def __init__(self, z, rp1, rp2, notice, working_directory):
        self.z = z
        self.rp1 = rp1
        self.rp2 = rp2
        self.notice = notice
        self.working_directory = working_directory

    def __call__(self, title):
        process_title(self.z, title, self.rp1, self.rp2, self.notice, self.working_directory)
        return u"Processor for " + title + u" complete."

def main():
    parser = argparse.ArgumentParser(description='Generates publicdocs project US Code files.')
    parser.add_argument('--ua', dest='useragent', action='store',
                        default='',
                        help='user agent for downloading files')
    parser.add_argument('--wd', '--working-dir', dest='working_directory', action='store',
                        default='working/',
                        help='working directory for temporary files generated by processing')
    parser.add_argument('--o', '--output-dir', dest='output_directory', action='store',
                        default='out/',
                        help='output directory for final files generated by processing')
    parser.add_argument('--clear-out', dest='clear_out', action='store_true',
                        help='clears the output directory first')
    parser.add_argument('--i', '--input-zip', dest='input_zip', action='store', type=file,
                        help='path to input zip file')
    parser.add_argument('--notice', dest='notice_file', action='store', type=file,
                        help='path to input NOTICE file')
    parser.add_argument('--rp1', dest='rp1', action='store',
                        help='First part of the release point id, ex. 114 in Public Law 114-195')
    parser.add_argument('--rp2', dest='rp2', action='store',
                        help='Second part of the release point id, ex. 195 in Public Law 114-195')
    parser.add_argument('--titles', dest='titles', nargs='*',
                        help='List of title numbers to process, or none to process all')

    args = parser.parse_args()
    if args.input_zip:
        zipinfo = process_zip(args.input_zip, args.working_directory)
        notice = args.notice_file.read()
        prep_output(args.working_directory)
        at = args.titles
        if not at:
            at = sorted("01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 05A 11A 18A 28a 50A".split())
        if len(at) > 1:
            pool = Pool(len(at))
            tp = title_processor(zipinfo, args.rp1, args.rp2, notice, args.working_directory)
            pool.map(tp, at)
        else:
            for title in at:
                process_title(zipinfo, title, args.rp1, args.rp2, notice, args.working_directory)
    else:
        print u"(FATAL) #### Could not determine operating mode"
        assert(False)

if __name__ == "__main__":
    main()
