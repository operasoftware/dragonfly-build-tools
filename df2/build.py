import re
import codecs
import os
import shutil
import tempfile
import sys
import zipfile
import base64
import StringIO
import urllib
import subprocess
from createmanifests import create_manifests

"""
uglifyjs is a python wrapper for uglifyjs.
See e.g. https://bitbucket.org/chrisk/uglifyjs

It can be any javascript minifyer. The required interface is:

    def minify(inpath, outpath, encoding="utf_8"):
        Minify input path to outputpath, optionally using encoding
    
    def minify_in_place(path, encoding="utf_8"):
        Minify path and write it to to the same location. Optionally use
        encoding
"""

try:
    import uglifyjs as jsminify
except ImportError:
    print "failed to import uglifyjs"
    import jsminify


_text_exts = (".js", ".html", ".xml", ".css")
_directive_exts = (".xml", ".html", ".xhtml") # files that may have <!-- command.. directives
_keyword_exts = (".css", ".js", ".xml", ".html", ".xhtml", ".txt") # files we will try to do keyword interpolation on
_license_exts = (".js", ".css") # extensions that should get a license
_img_exts = (".png", ".jpg", ".gif")
_script_ele = u"<script src=\"%s\"/>\n"
_style_ele = u"<link rel=\"stylesheet\" href=\"%s\"/>\n"
_base_url = u"<base href=\"%s\" />\n"
_re_command = re.compile("""\s?<!--\s+command\s+(?P<command>\w+)\s+"?(?P<target>.*?)"?\s*(?:if\s+(?P<neg>not)?\s*(?P<cond>\S+?))?\s*-->""")
_re_comment = re.compile("""\s*<!--.*-->\s*""")
_re_script = re.compile("\s?<script +src=\"(?P<src>[^\"]*)\"")
_re_css = re.compile("\s?<link +rel=\"stylesheet\" +href=\"(?P<href>[^\"]*)\"/>")
_re_condition = re.compile("\s+if\s+(not)? (.*)")
_re_client_lang_file = re.compile("^client-([a-zA-Z\-]{2,5})\.xml$")
_re_linked_source = re.compile(r"(?:src|href)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")

_concatcomment =u"""
/* dfbuild: concatenated from: %s */
"""

def _process_directive_files(dirpath, vars):
    for base, dirs, files in os.walk(dirpath, topdown=True):
        for file in [ os.path.join(dirpath, base, f) for f in files if f.endswith(_directive_exts) ]:
            _process_directives(dirpath, file, vars)


def _process_directives(root, filepath, vars):
    """
    Process all directives in the file filepath. The root dir is in root
    
    TODO: Refactor this to use separate functions for each directive and
    just pass in a context for it to keep stuff in.
    """
    file = open(filepath)

    tmpfd, tmppath = tempfile.mkstemp(".tmp", "dfbuild.")
    tmpfile = os.fdopen(tmpfd, "w")
    
    known_files = {}
    current_css_file = None
    current_js_file = None
    for line in file:
        match_cmd = _re_command.search(line)
        match_css = _re_css.search(line)
        match_js = _re_script.search(line)
        match_comment = _re_comment.search(line)
        
        
        if match_cmd:
            cmd, target, neg, cond = match_cmd.groups()
            if cond: # check if this directive is conditional
                c = bool(cond in vars and vars[cond])
                if neg:
                    c = not c
                    
                if not c: # the condition was not met, skip rule
                    continue

            # at this point the rule will be honoured
            if cmd == "concat_css":
                if target in ["off", "false", "no"]:
                    current_css_file = None
                elif target in known_files:
                    current_css_file = target
                else:
                    known_files[target] = []
                    current_css_file = target
                    tmpfile.write(_style_ele % target)
                continue
            elif cmd == "concat_js":
                if target in ["off", "false", "no"]:
                    current_js_file = None
                elif target in known_files:
                    current_js_file = target
                else:
                    known_files[target] = []
                    current_js_file = target
                    tmpfile.write(_script_ele % target)
                continue
            elif cmd == "set_rel_base_url" and \
               vars.has_key("base_url") and vars["base_url"]:
                tmpfile.write(_base_url % vars["base_url"])
                continue
            else: # some other unknown command! Let fall through so line is written
                pass
        elif match_comment:
            continue
        elif match_css:
            if current_css_file:
                known_files[current_css_file].append(match_css.group("href"))
                continue
        elif match_js:
            if current_js_file:
                known_files[current_js_file].append(match_js.group("src"))
                #fixme: The following continue should have been on the same level as this comment. However, that causes lang files to be included. must fix
            continue
        elif line.isspace():
            continue

        tmpfile.write(line)
        
    tmpfile.close()
    
    # write back the temp stuff, which is now the authoritative stuff:
    
    shutil.copy(tmppath, filepath)
    os.unlink(tmppath)

    for outfile, contentfiles in known_files.items():
        outpath = os.path.join(root, outfile)
        outdir = os.path.dirname(outpath)

        if not os.path.isdir(outdir): 
            os.makedirs(outdir)

        fout_path = os.path.join(root, outfile)
        fout = codecs.open(fout_path, "w", encoding="utf_8_sig")
        for infile in contentfiles:
            fout.write(_concatcomment % infile)
            fin = codecs.open(os.path.join(root, infile), "r", encoding="utf_8_sig")
            fout.write(fin.read())
            fin.close()
            os.unlink(os.path.join(root, infile))
        fout.close()

def _clean_dir(root, exclude_dirs, exclude_files):
    """
    Remove anything in either of the blacklists, then remove all empty
    directories under root and its children
    """
    exclude_files = [os.path.normpath(os.path.join(root, f)) for f in exclude_files ]
    exclude_dirs = [os.path.normpath(os.path.join(root, d)) for d in exclude_dirs ]

    # first pass, remove blacklisted files
    for base, dirs, files in os.walk(root, topdown=True):
        if base in exclude_dirs:
            shutil.rmtree(base)
            continue
        
        for file in files:
            absfile = os.path.abspath(os.path.join(base, file))
            if absfile in exclude_files and os.path.isfile(absfile):
                os.unlink(absfile)

    # second pass, remove empty dirs
    for base, dirs, files in os.walk(root, topdown=True):
        if not dirs and not files:
            os.rmdir(base)


def _add_license(root, license_path="include-license.txt"):
    """
    Read a license from license_path and append it to all files under root
    whose extension is in _license_exts.
    """
    if not os.path.isfile(license_path):
        return
    
    lfile = codecs.open(license_path, "r", encoding="utf_8_sig")
    license = lfile.read()
    lfile.close()
    
    license_files = []
    for base, dirs, files in os.walk(root):
        license_files.extend( [ os.path.join(base, f) for f in files if f.endswith(_license_exts)] )
    
    for f in license_files:
        source = codecs.open(f, "r", encoding="utf_8_sig")
        tmpfd, tmppath = tempfile.mkstemp(".tmp", "dfbuild.")
        tmpfile = os.fdopen(tmpfd, "w")
        wrapped = codecs.getwriter("utf_8_sig")(tmpfile)
        wrapped.write(license)
        wrapped.write("\n")
        wrapped.write(source.read())
        source.close()
        tmpfile.close()
        shutil.copy(tmppath, f)
        os.unlink(tmppath)


def _add_keywords(root, keywords):
    """
    Do keyword replacement on all files in and under root which has an
    extension in _keyword_exts. keywords is a dictionary, the key will be
    replaced with the value.
    """
    keyword_files = []
    for base, dirs, files in os.walk(root):
        keyword_files.extend( [ os.path.join(base, f) for f in files if f.endswith(_keyword_exts)] )
    
    for f in keyword_files:
        source = codecs.open(f, "r", encoding="utf_8_sig")
        tmpfd, tmppath = tempfile.mkstemp(".tmp", "dfbuild.")
        tmpfile = os.fdopen(tmpfd, "w")
        wrapped = codecs.getwriter("utf_8_sig")(tmpfile)
        for line in source:
            for key, val in keywords.items():
                line = line.replace(key, val)
            wrapped.write(line)
            
        source.close()
        tmpfile.close()
        shutil.copy(tmppath, f)
        os.unlink(tmppath)

def _is_utf8(path):
    """Check if file at path is utf8. Note that this only checks for a
    utf8 BOM, nothing more
    """
    if not os.path.isfile(path): return None
    f = open(path, "rb")
    return "test-scripts" in path and True or f.read(3) == codecs.BOM_UTF8
    
def _minify_buildout(src, blacklist=[]):
    """
    Run minification on all javascript files in directory src. Minification
    is done in-place, so the original file is replaced with the minified one.
    """
    for base, dirs, files in os.walk(src):
        bl = [d for d in dirs if d in blacklist]
        while bl:
            dirs.pop(dirs.index(bl.pop()))

        for file in [f for f in files if f.endswith(".js")]:
            abs = os.path.join(base, file)
            jsminify.minify_in_place(abs)
            
def _localize_buildout(src, langdir, option_minify):
    """Make a localized version of the build dir. That is, with one
    script.js for each language, with a prefix suffix for each language
    src: directory containing the finished build
    language: dir containing language files. NOT in build dir!
    
    Note, this function knows much more than it should about the structure
    of the build. The whole thing should possibly be refactored :(
    """
    tmpfiles = []
    scriptpath = os.path.normpath(os.path.join(src, "script/dragonfly.js"))
    fp = codecs.open(scriptpath, "r", encoding="utf_8_sig")
    script_data = fp.read()
    fp.close()
 
    clientpath = os.path.normpath(os.path.join(src, "client-en.xml"))
    fp = codecs.open(clientpath, "r", encoding="utf_8_sig")
    clientdata = fp.read()
    fp.close()

    # Grab all english data. Will be put in front of localized strings so
    # there are fallbacks
    englishfile = os.path.join(langdir, "ui_strings-en.js")
    fp = codecs.open(englishfile, "r", encoding="utf_8_sig")
    englishdata = fp.read()
    fp.close()
    
    langnames = [f for f in os.listdir(langdir) if f.startswith("ui_strings-") and f.endswith(".js") ]
    langnames = [f.replace("ui_strings-", "").replace(".js", "") for f in langnames]
    
    for lang, newscriptpath, newclientpath, path in [ (ln, "script/dragonfly-"+ln+".js", "client-"+ln+".xml", os.path.join(langdir, "ui_strings-"+ln+".js")) for ln in langnames ]:
        newscript = codecs.open(os.path.join(src,newscriptpath), "w", encoding="utf_8_sig")
        newclient = codecs.open(os.path.join(src, newclientpath), "w", encoding="utf_8_sig")

        if not option_minify:
            newscript.write(_concatcomment % englishfile)
        newscript.write(englishdata)
        langfile = codecs.open(path, "r", encoding="utf_8_sig")
        if not option_minify:
            newscript.write(_concatcomment % path)
        newscript.write(langfile.read())
        newscript.write(script_data)
        newclient.write(clientdata.replace("dragonfly.js", "dragonfly" + "-" + lang +".js"))
        newclient.close()
        langfile.close()
        newscript.close()
        
    os.unlink(os.path.join(src, "script/dragonfly.js"))
    while tmpfiles:
        os.unlink(tmpfiles.pop())
        

def _get_bad_encoding_files(src):
    """Check the source directory if it passes the criteria for a valid
    build. This means all files should be utf8 with a bom and all language
    strings present in the sources should be present in all the language
    files"""
    files = os.walk(src)
    
    bad = []
    for base, dirs, files in os.walk(src):
        for file in [f for f in files if f.endswith(_text_exts)]:
            abs = os.path.join(base, file)
            if not _is_utf8(abs): bad.append(abs)
            
    return bad

def _get_string_keys(path):
    """Grab all the string keys of out a language file"""
    re_key = re.compile("^ *ui_strings\.([^ =]*)")
    fp = codecs.open(path, "r", "utf_8_sig")
    lang_keys = set()
    for line in fp:
        lang_keys.update(re_key.findall(line))
    fp.close()
    return lang_keys
 
def _get_missing_strings(path, master):
    """Get the differences between the set of all strings and the
    strings in path"""
    keys = _get_string_keys(path)
    diff = master - keys
    return diff

def _get_missing_strings_for_dir(stringsdir, masterlang):
    stringfiles = os.listdir(stringsdir)
    masterfile = os.path.join(stringsdir, "ui_strings-%s.js" % masterlang )
    missing = {}
    if not os.path.isfile(masterfile): return None

    masterstrings = _get_string_keys(masterfile)
    
    for path, lang in [(f, f[-5:-3]) for f in stringfiles]:
        if lang==masterlang: continue
        langfile = os.path.join(stringsdir, "ui_strings-%s.js" % lang)
        if not os.path.isfile(langfile):
            continue
        s = _get_missing_strings(langfile, masterstrings)

        if s:
            missing[lang] = s
            
    return missing

def _clobbering_copytree(src, dst, symlinks=False):
    """This is a modified version of copytree from the shutil module in
    the standard library. This version will allow copying to existing folders
    and will clobber existing files. USE WITH CAUTION!
    Original docstring follows:
    
    Recursively copy a directory tree using copy2().

    The destination directory must not already exist.
    If exception(s) occur, an Error is raised with a list of reasons.

    If the optional symlinks flag is true, symbolic links in the
    source tree result in symbolic links in the destination tree; if
    it is false, the contents of the files pointed to by symbolic
    links are copied.

    XXX Consider this example code rather than the ultimate tool.

    """
    names = os.listdir(src)
    if not os.path.isdir(dst):
        os.makedirs(dst)

    errors = []
    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                _clobbering_copytree(srcname, dstname, symlinks)
            else:
                shutil.copy2(srcname, dstname)
            # XXX What about devices, sockets etc.?
        except (IOError, os.error), why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error, err:
            errors.extend(err.args[0])
    try:
        shutil.copystat(src, dst)
    except WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError, why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise Error, errors

def _data_uri_from_path(path):
    if os.path.isfile(path):
        fp = open(path, "rb")
        return "'data:image/png;charset=utf-8;base64," + base64.b64encode(fp.read()) + "'"
    else:
        return None

def _find_file_path(base, file_name):
    for dirpath, dirs, fns in os.walk(base):
        for fn in fns:
            if fn == file_name:
                return os.path.join(dirpath, fn)
    return None

def URI_to_os_path(path):
    return os.path.join(*[urllib.unquote(part) for part in path.split('/')])

def _convert_imgs_to_data_uris(src):
    re_img = re.compile(r""".*?url\((['"]?(.*?)['"]?)\)""")
    deletions = []
    for base, dirs, files in os.walk(src):
        for path in [ os.path.join(base, f) for f in files if f.endswith(".css") ]:
            fp = codecs.open(path, "r", "utf_8_sig")
            dirty = False
            temp = StringIO.StringIO()
            for line in fp:
                match = re_img.findall(line)
                if match:
                    for full, stripped in match:
                        file_path = os.path.join(base, URI_to_os_path(stripped))
                        if not os.path.isfile(file_path):
                            # src is actually the target destination of the build
                            # that means the relations of css and according images 
                            # are lost. Clashing filenames will cause problems.
                            parts = stripped.split('/')
                            file_name = parts[len(parts) - 1]
                            file_path = _find_file_path(src, file_name)
                        uri = ""
                        if file_path:
                            deletions.append(file_path)
                            uri = _data_uri_from_path(file_path)
                        if uri:
                            temp.write(line.replace(full, uri).encode("ascii"))
                        else:
                            if not stripped.startswith("data:"):
                                print "no data uri for path:", os.path.join(base, URI_to_os_path(stripped)) 
                            temp.write(line.encode("ascii"))
                            dirty = True
                else:
                    temp.write(line.encode("ascii"))
                    dirty = True

            if dirty:
                fp.close()
                fp = codecs.open(path, "w", encoding="utf_8_sig")
                temp.seek(0)
                fp.write(temp.read().encode("utf-8"))
                fp.close()
                
    for path in deletions:
        if os.path.isfile(path): os.unlink(path)

def _make_rel_url_path(src, dst):
    """src is a file or dir which wants to adress dst relatively, calculate
    the appropriate path to get from here to there."""
    srcdir = os.path.abspath(src + "/..")
    dst = os.path.abspath(dst)

    # For future reference, I hate doing dir munging with string operations
    # with a fiery passion, but pragmatism won out over making a lib.. .
    
    common = os.path.commonprefix((srcdir, dst))
    
    reldst = dst[len(common):]
    srcdir = srcdir[len(common):]

    newpath = re.sub(""".*?[/\\\]|.+$""", "../", srcdir) or "./"
    newpath = newpath + reldst
    newpath = newpath.replace("\\", "/")
    newpath = newpath.replace("//", "/")
    return newpath

def make_archive(src, dst, in_subdir=True):
    """This simply packs up the contents in the directory src into a zip
    archive dst. This is here so we can easily zip stuff from build files
    without forcing the user to install a command line zip tool. If in_subdir
    is true, the archive will contain a top level directory with the same
    name as the archive, without the extension. If it is false, the files are
    put in the root of the archive
    """
    src = os.path.abspath(src)
    z = zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED)
    
    if in_subdir:
        subdir = os.path.basename(dst)
        subdir = subdir[:subdir.rfind(".")]
        subdir = subdir + "/"
    else:
        subdir=""
    
    for base, dirs, files in os.walk(src):
        for file in files:
            abs = os.path.join(base, file)
            rel = subdir + os.path.join(base, file)[len(src)+1:]
            z.write(abs, rel)

    z.close()

def make_build_archive(src, dest_dir, file_name):
    dest = os.path.join(dest_dir, file_name.replace(".xml", ".zip"))
    z = zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED)
    files = [file_name]

    with open(os.path.join(src, file_name), 'r') as f:
        content = f.read()
        for match in _re_linked_source.finditer(content):
            path = os.path.normpath(match.group(1) or match.group(2))
            ext = path
            if not ext.startswith('.'):
                empty, ext = os.path.splitext(path)
            if ext in [".css", ".js"]:
                files.append(path)

    for path in files:
        z.write(os.path.join(src, path), path)
    
    z.close()
    

def export(src, dst, process_directives=True, keywords={},
           exclude_dirs=[], exclude_files=[], directive_vars={}):
    """
    Build from a directory to a directory.
    
    src: Source dir to build from
    dst: destination directory to build to
    process_directives: if true, process <!-- command.. directives in html/xml files
    Keywords: key/value pairs used for keyword replacement on the sources. As in,
        if the source files contain $date$ the keywords dict could contain
        {"$date$": "23.09.08"}, to insert that date into the sources.
    exclude_dirs: directoriy blacklist. Will not be included in the build
    exclude_files: file blacklist. Will not be included in the build
    license: path to a license file to append to sources
    directive_vars: a dictionary that will passed on to the diretive handling.
        Can be used to control the handling of the directives
    """

    src = os.path.abspath(src); # make sure it's absolute

    # get a temporary place to do stuff
    tmpbase = tempfile.mkdtemp(".tmp", "dfbuild.")
    ## this is kinda dumb but copytree always copy to a non-extant subdir
    tmpdir = os.path.join(tmpbase, "src")
    shutil.copytree(src, tmpdir)

    if process_directives:
        _process_directive_files(tmpdir, directive_vars)
        
    # remove empty directories and stuff in the blacklist
    _clean_dir(tmpdir, exclude_dirs, exclude_files)
        
    if keywords:
        _add_keywords(tmpdir, keywords)
        
    #copy the stuff to its final destination and get rid of temp copy:
    if not os.path.isdir(dst):
        os.mkdir(dst)
    
    # stupid copy function to get around the must-put-in-subdir thingy in shutil.copytree
    for entry in os.listdir(tmpdir):
        path = os.path.join(tmpdir, entry)
        if os.path.isdir(path):
            _clobbering_copytree(path, os.path.join(dst, entry))
        else:
            shutil.copy(os.path.join(tmpdir,entry), dst)

    shutil.rmtree(tmpbase)

def _ansi2utf8(path):
    f = codecs.open(path, 'r', 'utf-8')
    c = f.read()
    f.close()
    f = codecs.open(path, 'w', 'utf_8_sig')
    f.write(c)
    f.close()

def main(argv=sys.argv):
    """
    Entry point when the script is called from the command line, not used
    as a module.
    """
    import optparse
    usage = """%prog [options] source [destination]
    
Destination can be either a directory or a zip file"""
    parser = optparse.OptionParser(usage)
    parser.add_option("-c", "--no-concat", dest="concat",
                      default=True, action="store_false",
                      help="Do NOT concatenate script and css")
    parser.add_option("-l", "--no-license", dest="license",
                      default=True, action="store_false",
                      help="Do NOT append license file to js and css. (license is taken from $cwd/include-license.txt")
    parser.add_option("-k", "--keyword", dest="kwlist",
                      default=None, type="string", action="append",
                      help="A key/value pair. All instances of key will be replaced by value in all files. More than one key/value is allowed by adding more -k switches", metavar="key=value")
    parser.add_option("-d", "--delete", default=False,
                      action="store_true", dest="overwrite_dst",
                      help="Delete the destination before copying to it. Makes sure that there are no files left over from previous builds. Is destructive!")
    parser.add_option("-t", "--translate", default=False,
                      action="store_true", dest="translate_build",
                      help="Apply translation changes to the finished build")
    parser.add_option("-s", "--no-string-check", default=True,
                      action="store_false", dest="check_strings",
                      help="Don't check validity of strings before building")
    parser.add_option("-e", "--no-enc-check", default=True,
                      action="store_false", dest="check_encodings",
                      help="Don't check encoding of files before building")
    parser.add_option("-m", "--minify", default=False,
                      action="store_true", dest="minify",
                      help="Minify the sources")
    parser.add_option("-u", "--no-data-uri", default=True,
                      action="store_false", dest="make_data_uris",
                      help="Don't generate data URIs for images in css")

    parser.add_option("-b", "--set-base", default=None,
                      type="string", dest="set_base",
                      help="""Set a base url in the document. """
                      """The value of the setting is the realative root in the """
                      """destination path. E.g. a the value "app" with the destination"""
                      """ "<some loca path>/app/core-2-5" will set the base url"""
                      """ to "/app/core-2-5/". The purpose is to ba able to rewrite"""
                      """ urls without breaking other urls of the rewritten document,"""
                      """ e.g. handling all different core version on the "/app/" path"""
                      """ without redirects.""")

    parser.add_option("--fixBOM", default=False,
                      action="store_true", dest="fix_BOM",
                      help="Try to convert ANSI to UTF8 with BOM. Use only with source.")

    options, args = parser.parse_args()
    globals()['options'] = options

    if len(args) == 1 and options.fix_BOM:
        bad = _get_bad_encoding_files(args[0])
        for path in bad:
            _ansi2utf8(path)
        return 0
    
    # Make sure we have a source and destination
    if len(args) != 2:
        parser.error("Source and destination argument is required")
    else:
        src, dst = args
    
    dirvars = {}
    
    if options.concat:
        exdirs = ["scripts", "ui-style", "ecma-debugger", "ui-strings"]
    else:
        exdirs = []
    
    if options.translate_build:
        dirvars["exclude_uistrings"]=True

    if options.set_base:
        path_segs = os.path.normpath(dst).split(os.sep)
        pos = path_segs.index(options.set_base)
        dirvars["base_url"] = pos > -1 and "/%s/" % "/".join(path_segs[pos:]) or ""
    
    # Parse the keyword definitons
    keywords = {}
    if options.kwlist:
        try:
            for kw in options.kwlist:
                key, val = kw.split("=")
                keywords[key] = val
        except ValueError:
            parser.error("""Could not parse keyword option: "%s" """ % kw)
    
    if options.translate_build and not options.concat:
        parser.error("""Can't translate when not concatenateing. use --no-concat OR --translate""")
    
    if options.check_encodings:
        bad = _get_bad_encoding_files(src)
        if bad:
            print "The following files do not seem to be UTF8 with BOM encoded:"
            for b in bad: print "\t%s" % b
            sys.exit()

    if options.check_strings:
        missingstrings = _get_missing_strings_for_dir(os.path.join(src, "ui-strings"), "en")
        if missingstrings==None:
            print "couldn't parse the master string list!"
            sys.exit()
        elif missingstrings:
            for lang, strings in missingstrings.items():
                print """Language "%s" is missing the following strings:""" % lang
                for s in strings: print "\t%s" % s
            sys.exit()
    
    if dst.endswith(".zip"): # export to a zip file
        if os.path.isfile(dst):
            if not options.overwrite_dst:
                parser.error("Destination exists! use -d to force overwrite")
            else:
                os.unlink(dst)

        tempdir = tempfile.mkdtemp(".tmp", "dfbuild.")
        export(src, tempdir, process_directives=options.concat, exclude_dirs=exdirs,
               keywords=keywords, directive_vars=dirvars)

        if options.translate_build:
            _localize_buildout(tempdir,
                               os.path.join(os.path.abspath(src), "ui-strings"),
                               options.minify)

        if options.make_data_uris:
            _convert_imgs_to_data_uris(dst)

        if options.minify:
            _minify_buildout(dst)

        if options.license:
            _add_license(tempdir)

        make_archive(tempdir, dst)
        shutil.rmtree(tempdir)

    else: # export to a directory
        if os.path.isdir(dst) and not options.overwrite_dst:
            parser.error("Destination exists! use -d to force overwrite")

        export(src, dst, process_directives=options.concat, exclude_dirs=exdirs,
               keywords=keywords, directive_vars=dirvars)

        if options.translate_build:
            _localize_buildout(dst,
                               os.path.join(os.path.abspath(src), "ui-strings"),
                               options.minify)

        if options.make_data_uris:
            _convert_imgs_to_data_uris(dst)
            # any remaining image in ui-images is not used
            img_dir = os.path.join(dst, 'ui-images')
            shutil.rmtree(img_dir)
 
        if options.minify:
            _minify_buildout(dst)

        if options.license:
            _add_license(dst)

        AUTHORS = os.path.join(src, '..', 'AUTHORS')
        if os.path.isfile(AUTHORS):
            shutil.copy(AUTHORS, os.path.join(dst, 'AUTHORS'))


 
def cmd_call(*args):
    return subprocess.Popen(args, 
                            stdout=subprocess.PIPE,
                            stdin=subprocess.PIPE,
                            stderr=subprocess.PIPE).communicate()

def fix_bom(args):
    bad = _get_bad_encoding_files(args.src)
    for path in bad:
        _ansi2utf8(path)
        print "BOM fixed for \"%s.\"" % path 
    return 0

def _get_profile(profiles, name):
    for p in profiles:
        if p == name:
            return profiles[p]
        for alias in profiles[p].get("alias", []):
            if alias == name:
                return profiles[p]
    return None

def build(args):
    build_config = args.config.get("build", {})
    profile = {}
    profile.update(build_config.get("default_profile", {}))
    target_profile = _get_profile(build_config.get("profiles", {}),
                                  args.profile)
    if target_profile == None:
        print "abort. profile \"%s\" not found in config." % args.profile
        return

    profile.update(target_profile)

    out, err = cmd_call('hg', 'up', args.tag)
    if err:
        print "abort.", err
        return

    print out.strip()
    out, err = cmd_call("hg", "log", 
                        "-r", args.tag, 
                        "--template", "{rev}:{node|short}")
    if err:
        print "abort.", err
        return

    print "updated to revision: ", out.strip()
    rev, short_hash = out.strip().split(":", 1)
    src = profile.get("src", None)
    dest = profile.get("dest", None)
    if not (src and dest):
        print "abort. missing \"src\" or \"dest\" in the profile."
        return
    
    src = os.path.abspath(os.path.normpath(src))
    dest = os.path.abspath(os.path.normpath(dest))

    if profile.get("verify_bom"):
        bad = _get_bad_encoding_files(src)
        if bad:
            print "abort.",
            print "the following files do not seem to be UTF8 with BOM encoded:"
            for b in bad: print "\t%s" % b
            return

    if os.path.isdir(dest) and not profile.get("force_overwrite"):
        print "abort.",
        print "destination exists! Set \"force_overwrite\" in the config file."
        return
    
    revision_name = "%s:%s, %s, %s" % (rev,
                                       short_hash,
                                       profile.get("name"),
                                       args.tag)
    dirvars = {}
    if profile.get("translate"):
        dirvars["exclude_uistrings"] = True
    
    export(src, dest,
           exclude_dirs=profile.get("copy_blacklist"),
           keywords={"$dfversion$": args.revision, "$revdate$": revision_name},
           directive_vars=dirvars)
    print "build exported."

    if profile.get("translate"):
        _localize_buildout(dest,
                           os.path.join(src, "ui-strings"),
                           profile.get("minify"))
        print "build translated."

    if profile.get("make_data_uris"):
        _convert_imgs_to_data_uris(dest)
        # any remaining image in ui-images is not used
        img_dir = os.path.join(dest, 'ui-images')
        shutil.rmtree(img_dir)
        print "data URIs created."

    if profile.get("minify"):
        _minify_buildout(dest, profile.get("minify_blacklist"))
        print "builds minified."

    if profile.get("license"):
        _add_license(dest)
        print "license added."

    client_lang_files = []
    for item in os.listdir(dest):
        if os.path.isfile(os.path.join(dest, item)):
            match = _re_client_lang_file.match(item)
            if match:
                client_lang_files.append((item, match.group(1)))

    if profile.get("create_zips"):
        zip_dir = os.path.abspath(os.path.normpath(profile.get("zips")))
        zip_target = os.path.join(zip_dir, "%s.%s" % (rev, short_hash))
        if not os.path.isdir(zip_target):
            os.makedirs(zip_target)

        for name, lang in client_lang_files:
            make_build_archive(dest, zip_target, name)
            print "build for %s zipped." % lang

    if profile.get("base_root_dir"):
        path_segs = dest.split(os.path.sep)
        pos = path_segs.index(profile.get("base_root_dir"))
        if pos > -1:
            base_url = "/%s/" % "/".join(path_segs[pos + 1:])
            base_url_tag = (_base_url % base_url).strip().encode("utf-8")
            cmd_base_url = "<!-- command set_rel_base_url -->"
    
            for name, lang in client_lang_files:
                path = os.path.join(dest, name)
                content = ""
                with open(path, 'rb') as f:
                    content = f.read()
                if content:
                    with open(path, 'wb') as f:
                        f.write(content.replace(cmd_base_url, base_url_tag, 1))
                else:
                    print "abort. could not set base URL in %s." % name
                    return
        
            print "base URLs set."

        else:
            print "abort. could not set the base URLs."
            return

    if profile.get("create_manifests"):
        try:
            root = profile.get("manifest_root").encode("utf-8")
            create_manifests(dest.encode("utf-8"), domain_token=root, tag=args.tag)
            print "app cache manifests created."
        except:
            print "abort. could not create the manifest files."
            return

    if profile.get("create_log"):
        log_dir = os.path.abspath(os.path.normpath(profile.get("logs")))
        start_rev = args.last_revision_log
        log_name = "%s.%s.log" % (rev, short_hash)

        if not os.path.isdir(log_dir): 
            os.makedirs(log_dir)
        
        if not start_rev:
            logs = sorted([(l, int(os.stat(os.path.join(log_dir, l)).st_mtime))
                           for l in os.listdir(log_dir)],
                           key=lambda item: item[1])
            last_log = logs and logs[-1][0] or None

            if last_log == log_name:
                last_log = logs[-2][0] if len(logs) > 1 else ""
            
            if last_log:
                start_rev = last_log.split(".")[1]

        if start_rev:
            out, err = cmd_call("hg", "log", 
                                "-r", "%s:%s" % (args.tag, start_rev), 
                                "--style", "changelog")
            if err:
                print "could not create a log.\n", err

            with open(os.path.join(log_dir, log_name), "w") as f:
                f.write(out)
                print "log %s created." % log_name
        else:
            print "not possible to find a start revision.",
            print "provide a start revision with the -l flag."

    AUTHORS = os.path.join(src, '..', 'AUTHORS')
    if os.path.isfile(AUTHORS):
        shutil.copy(AUTHORS, os.path.join(dest, 'AUTHORS'))
    
    out, err = cmd_call('hg', 'up', 'tip')
    if err:
        print "could not update to tip.\n", err
    else:
        print "updated repository to tip."
            
def setup_subparser(subparsers, config):
    subp = subparsers.add_parser('build', help="Build Dragonfly.")
    subp.add_argument('profile',
                      nargs="?",
                      default="default", 
                      help="""The profile to build. The profile is
                              defined in the config file.""")
    subp.add_argument('--revision', '-r', 
                      required=False,
                      default="",
                      help="The Dragonfly revision ID.")
    subp.add_argument('-tag', '-t', 
                      required=False,
                      default="tip",
                      help="""An optional revision tag for the build. 
                              Default is "tip".""")
    subp.add_argument('--last-revision-log', '-l', 
                      required=False,
                      default=None,
                      help="""An optional revision id for the log range. 
                              Log starts with the build tag.
                              Default is the last log in the "logs" directory. 
                              If the last log starts with the current build tag
                              the log is created from the previous log 
                              (build recreated). If there is no log and the 
                              argument is not set no log is created.""")
    subp.set_defaults(func=build)

    subp = subparsers.add_parser('fixBOM', help="Add a BOM in all JS source files.")
    subp.add_argument('src', help="""The source path.""")
    subp.set_defaults(func=fix_bom)

if __name__ == "__main__":
    sys.exit(main())
 
