#!/usr/bin/env python

import cmd, contextlib, functools, getpass, os, pprint, random, re, sys, time
import bs4, difflib, execjs, json, requests
from datetime import datetime

class Magic( object ):
    bunnies = [
"""
  (\(\\
 (='.')
o(__")")""",

"""
(\__/)
(='.'=)
(")_(")""",

"""
 (\_/)
=(^.^)=
(")_(")""",

"""
(\ /)
( . .)
c(")(")""",

"""
(\__/)
(>'.'<)
(")_(")""",

"""
++++++++++++
|  LITTLE  |
|  BUNNY   |
|  LOVES   |
|   YOU    |
|    -xt2  |
++++++++++++
(\__/)  ||
(>'.'<) ||
(")_(") //""",

"""
   __//
  /.__.\  oops
  \ \/ /
__/    \\
\-      )
 \_____/
___|_|____
   " " """,
    ]
    def __init__( self ):
        self.motd = random.choice( self.bunnies )[ 1: ]

    def magic( self, msg ):
        return self.__owl( msg )

    def __owl( self, msg ):
        return """,___,\n[O.o]  %s\n/)__)\n-"--"-""" % msg

class Problem( object ):
    def __init__( self, pid, slug, rate, freq, status=None ):
        self.loaded = False
        self.pid = pid
        self.slug = slug
        self.rate = rate
        self.freq = freq
        self.status = status
        self.topics = []
        self.desc = self.code = self.test = self.html = ''
        self.record = History( slug )

    def __str__( self ):
        if self.solved:
            s = ' '
        elif self.failed:
            s = 'x'
        else:
            s = '*'
        s += '%3d %s' % ( self.pid, self.slug )
        return s

    @property
    def solved( self ):
        return self.status == 'ac'

    @solved.setter
    def solved( self, x ):
        self.status = 'ac' if x else 'notac'

    @property
    def failed( self ):
        return self.status == 'notac'

    @property
    def todo( self ):
        return not self.status

    @property
    def tags( self ):
        l = filter( lambda x: x != '#', self.topics )
        if not self.todo:
            l.append( str( self.record ) )
        return ', '.join( l ).title()

class Solution( object ):
    def __init__( self, pid, runtime, code ):
        self.pid = pid
        self.runtime = runtime
        self.code = code

    def __str__( self ):
        s = '[%d ms]\n' % self.runtime
        for i, l in enumerate( self.code.splitlines() ):
            s += '%3d %s\n' % ( i, l )
        return s

class Result( object ):
    def __init__( self, sid, result ):
#       pprint.pprint( result )
        self.sid = sid
        self.success = False
        self.fintime = None

        def split( s ):
            return s.splitlines() if type( s ) in [ str, unicode ] else s

        self.input = result.get( 'last_testcase', result.get( 'input', '' ) )
        self.output = split( result.get( 'code_output', '' ) )
        self.expected = split( result.get( 'expected_output', '' ) )
        self.debug = split( result.get( 'std_output' ) )

        self.result = result.get( 'code_answer', [] )
        if not self.result:
            total = result.get( 'total_testcases' )
            passed = result.get( 'total_correct' )
            if total:
                self.result.append( "%d/%d tests passed" % ( passed, total ) )

        self.errors = []
        for e in [ 'compile_error', 'runtime_error', 'error' ]:
            m = result.get( e )
            if m:
                self.errors.append( m )

        status = result.get( 'status_code' )
        if status == 10:
            self.success = True
        elif status == 12:
            self.errors.append( 'Memory Limit Exceeded' )
        elif status == 13:
            self.errors.append( 'Output Limit Exceeded' )
        elif status == 14:
            self.errors.append( 'Time limit Exceeded' )

        ts = result.get( 'status_runtime', '' ).replace( 'ms', '' ).strip()
        self.runtime = int( ts ) if ts.isdigit() else 0

    def __str__( self ):
        limit = 25
        s = '\n'.join( self.errors )
        if s:
            s += '\n'

        if self.result:
            s += 'Result: '
            s += ', '.join( self.result ) + '\n'

        if self.input:
            s += 'Input: ' + ','.join( self.input.splitlines() ) + '\n'

        if self.output:
            s += 'Output:'
            s += '\n' if len( self.output ) > 1 else ' '
            s += '\n'.join( self.output[ : limit ] ) + '\n'

        if self.expected:
            s += 'Expected:'
            s += '\n' if len( self.expected ) > 1 else ' '
            s += '\n'.join( self.expected[ : limit ] ) + '\n'

        if self.debug:
            s += 'Debug:'
            s += '\n' if len( self.debug ) > 1 else ' '
            s += '\n'.join( self.debug[ : limit ] ) + '\n'

        if self.runtime:
            s += 'Runtime: %d ms' % self.runtime + '\n'

        if self.fintime:
            m, sec = self.fintime / 60, self.fintime % 60
            s += 'Finish Time: %d min %d sec' % ( m, sec ) + '\n'

        return s.strip( '\n' )

class History( object ):
    def __init__( self, slug ):
        self.slug = slug
        self.submissions = []
        self.passed = 0

    @property
    def sid( self ):
        for e in reversed( self.submissions ):
            return e[ 0 ]
        return None

    @property
    def total( self ):
        return len( self.submissions )

    def add( self, sid, lang, status, timestamp='Now' ):
        if status == 'Accepted':
            self.passed += 1
        self.submissions.append( ( sid, lang, status, timestamp ) )

    def __str__( self ):
        return '%d/%d' % ( self.passed, self.total ) if self.total else ''

class Session( object ):
    def __init__( self, sid, name, active ):
        self.sid = sid
        self.name = name if name else '#'
        self.active = active

    def __str__( self ):
        return '*' if self.active else '' + self.name

class OJMixin( object ):
    url = 'https://leetcode.com'
    langs = [ 'c', 'cpp', 'golang', 'java', 'javascript', 'python', 'scala' ]
    lang = 'python'

    @property
    def suffix( self ):
        suffixes = { 'golang': 'go', 'javascript': 'js', 'python': 'py' }
        return suffixes.get( self.lang, self.lang )

    @property
    def language( self ):
        languages = {
            'cpp': 'C++',
            'csharp' : 'C#',
            'golang' : 'Go',
            'javascript' : 'JavaScript'
        }
        return languages.get( self.lang, self.lang.title() )

    session, loggedIn = requests.session(), False

    def login( self ):
        url = self.url + '/accounts/login/'
        name = { 'name' : 'csrfmiddlewaretoken' }
        username = raw_input( 'Username: ' )
        password = getpass.getpass()

        self.session.cookies.clear()
        resp = self.session.get( url )

        soup = bs4.BeautifulSoup( resp.text, 'html.parser' )
        for e in soup.find_all( 'input', attrs=name ):
            csrf = e[ 'value' ]
            break

        headers = { 'referer' : url }
        data = {
            'login': username,
            'password': password,
            'csrfmiddlewaretoken': csrf
        }

        resp = self.session.post( url, data, headers=headers )
        if self.session.cookies.get( 'LEETCODE_SESSION' ):
            self.loggedIn = True
            print 'Welcome %s!' % username
        else:
            self.loggedIn = False

    def parse_sessions( self, resp ):
        sd = {}
        for s in json.loads( resp.text ).get( 'sessions', [] ):
            sid, name, active = s[ 'id' ], s[ 'name' ] or '#', s[ 'is_active' ]
            sd[ name ] = Session( sid, name, active )
        return sd

    def get_sessions( self ):
        url = self.url + '/session/'
        headers = {
                'referer' : url,
                'content-type' : 'application/json',
                'x-csrftoken' : self.session.cookies[ 'csrftoken' ],
                'x-requested-with' : 'XMLHttpRequest',
        }
        resp = self.session.post( url, json={}, headers=headers )
        return self.parse_sessions( resp )

    def create_session( self, name ):
        url = self.url + '/session/'
        headers = {
                'referer' : url,
                'content-type' : 'application/json',
                'x-csrftoken' : self.session.cookies[ 'csrftoken' ],
                'x-requested-with' : 'XMLHttpRequest',
        }
        data = { 'func': 'create', 'name': name, }
        resp = self.session.put( url, json=data, headers=headers )
        return self.parse_sessions( resp )

    def activate_session( self, sid ):
        url = self.url + '/session/'
        headers = {
                'referer' : url,
                'content-type' : 'application/json',
                'x-csrftoken' : self.session.cookies[ 'csrftoken' ],
                'x-requested-with' : 'XMLHttpRequest',
        }
        data = { 'func': 'activate', 'target': sid, }
        resp = self.session.put( url, json=data, headers=headers )
        return self.parse_sessions( resp )

    def get_tags( self ):
        url = self.url + '/problems/api/tags/'

        resp = self.session.get( url )
        data = json.loads( resp.text )

        topics = {}
        for e in data.get( 'topics' ):
            t = e.get( 'slug' )
            ql = e.get( 'questions' )
            topics[ t ] = ql

        companies = {}
        for e in data.get( 'companies' ):
            c = e.get( 'slug' )
            ql = e.get( 'questions' )
            companies[ c ] = set( ql )

        return ( topics, companies )

    def get_problems( self ):
        url = self.url + '/api/problems/algorithms/'

        resp = self.session.get( url )

        problems = {}
        for e in json.loads( resp.text ).get( 'stat_status_pairs' ):
            i = e.get( 'stat' ).get( 'question_id' )
            s = e.get( 'stat' ).get( 'question__title_slug' )
            a = e.get( 'stat' ).get( 'total_acs' )
            n = e.get( 'stat' ).get( 'total_submitted' )
            f = e.get( 'frequency' )
            t = e.get( 'status' )
            ar = float( a ) / n
            problems[ i ] = Problem( pid=i, slug=s, rate=ar, freq=f, status=t )

        return problems

    def strip( self, s ):
        return s.replace( '\r', '' ).encode( 'ascii', 'ignore' )

    def get_problem( self, p ):
        url = self.url + '/problems/%s/description/' % p.slug
        cls = { 'class' : 'question-description' }
        js = r'var pageData =\s*(.*?);'

        resp = self.session.get( url )

        soup = bs4.BeautifulSoup( resp.text, 'html.parser' )
        for e in soup.find_all( 'div', attrs=cls ):
            p.desc = self.strip( e.text )
            p.html = self.strip( e.prettify() )
            break

        for s in re.findall( js, resp.text, re.DOTALL ):
            v = execjs.eval( s )
            for cs in v.get( 'codeDefinition' ):
                if cs.get( 'text' ) == self.language:
                    p.code = self.strip( cs.get( 'defaultCode', '' ) )
            p.test = v.get( 'sampleTestCase' )
            break

        if not p.todo:
            p.code = self.get_latest_solution( p )
            p.record = self.get_history( p )

        p.loaded = bool( p.desc and p.test and p.code )

    def get_latest_solution( self, p ):
        url = self.url + '/submissions/latest/'
        referer = self.url + '/problems/%s/description/' % p.slug
        headers = {
                'referer' : referer,
                'content-type' : 'application/json',
                'x-csrftoken' : self.session.cookies[ 'csrftoken' ],
                'x-requested-with' : 'XMLHttpRequest',
        }
        data = {
            'qid': p.pid,
            'lang': self.lang,
        }

        resp = self.session.post( url, json=data, headers=headers )

        try:
            code = self.strip( json.loads( resp.text ).get( 'code' ) )
        except ValueError:
            code = ''
        return code

    def get_solution( self, pid, runtime ):
        url = self.url + '/submissions/api/detail/%d/%s/%d/' % \
                ( pid, self.lang, runtime )

        resp = self.session.get( url )
        data = json.loads( resp.text )
        code = data.get( 'code' )

        return Solution( pid, runtime, code )

    def get_solutions( self, pid, sid, limit=10 ):
        url = self.url + '/submissions/detail/%s/' % sid
        js = r'var pageData =\s*(.*?);'

        resp = self.session.get( url )

        def diff( a, sl ):
            for b in sl:
                r = difflib.SequenceMatcher( a=a.code, b=b.code ).ratio()
                if r >= 0.9:
                    return False
            return True

        solutions = []
        for s in re.findall( js, resp.text, re.DOTALL ):
            v = execjs.eval( s )
            try:
                df = json.loads( v.get( 'distribution_formatted' ) )
                if df.get( 'lang' ) == self.lang:
                    for e in df.get( 'distribution' )[ : limit ]:
                        t = int( e[ 0 ] )
                        sln = self.get_solution( pid, t )
                        if diff( sln, solutions ):
                            solutions.append( sln )
                    break
            except ValueError:
                pass

        return solutions

    def get_solution_runtimes( self, sid ):
        url = self.url + '/submissions/detail/%s/' % sid
        js = r'var pageData =\s*(.*?);'

        resp = self.session.get( url )
        runtimes = []

        for s in re.findall( js, resp.text, re.DOTALL ):
            v = execjs.eval( s )
            try:
                df = json.loads( v.get( 'distribution_formatted' ) )
                if df.get( 'lang' ) == self.lang:
                    for t, n in df.get( 'distribution' ):
                        runtimes.append( ( int( t ), float( n ) ) )
            except ValueError:
                pass

        return runtimes

    def test_solution( self, p, code, tests='', full=False ):
        if full:
            epUrl, sidKey = 'submit/', 'submission_id'
        else:
            epUrl, sidKey = 'interpret_solution/', 'interpret_id'

        url = self.url + '/problems/%s/%s/' % ( p.slug, epUrl )
        referer = self.url + '/problems/%s/description/' % p.slug
        headers = {
                'referer' : referer,
                'content-type' : 'application/json',
                'x-csrftoken' : self.session.cookies[ 'csrftoken' ],
                'x-requested-with' : 'XMLHttpRequest',
        }
        data = {
            'judge_type': 'large',
            'lang' : self.lang,
            'test_mode' : False,
            'question_id' : str( p.pid ),
            'typed_code' : code,
            'data_input': tests,
        }

        resp = self.session.post( url, json=data, headers=headers )
        try:
            sid = json.loads( resp.text ).get( sidKey )
            result = self.get_result( sid )
        except ValueError:
            result = None

        return result

    def get_result( self, sid, timeout=30 ):
        url = self.url + '/submissions/detail/%s/check/' % sid

        for i in xrange( timeout ):
            time.sleep( 1 )
            resp = self.session.get( url )
            data = json.loads( resp.text )
            if data.get( 'state' ) == 'SUCCESS':
                break
        else:
            data = { 'error': '< network timeout >' }

        return Result( sid, data )

    def get_history( self, p ):
        url = self.url + '/api/submissions/%s/' % p.slug

        resp = self.session.get( url )

        r = History( p.slug )
        for e in json.loads( resp.text ).get( 'submissions_dump' ):
            sid = e.get( 'url' ).split( '/' )[ 3 ]
            lang = e.get( 'lang' )
            s = e.get( 'status_display' )
            t = e.get( 'time' )
            r.add( sid=sid, lang=lang, status=s, timestamp=t )

        return r

class Html( object ):
    def __init__( self, p ):
        self.p = p

    @staticmethod
    def header():
        with open( 'header.html', 'r' ) as f:
            s = f.read()
        return s + '<body><div class="container">'

    @staticmethod
    def tail():
        return '</div></body>'

    @property
    def title( self ):
        p = self.p
        s = '<h4>' + str( p.pid ) + ' '+ p.slug.replace( '-', ' ' ).title() + '</h4>'
        if p.todo:
            s = '<div class="bg-primary text-white">' + s + '</div>'
        elif p.failed or p.rate < 0.34:
            s = '<div class="bg-danger text-white">' + s + '</div>'
        else:
            s = '<div>' + s + '</div>'
        return s

    @property
    def tags( self ):
        p = self.p
        return '<div><mark>' + p.tags + '</mark></div>' if p.tags else ''

    @property
    def desc( self ):
        return self.p.html

    @property
    def code( self ):
        p = self.p
        return '<pre><code>' + p.code + '</code></pre>' if p.solved else ''

    def __str__( self ):
        return ''.join( [ self.title, self.tags, self.desc, self.code ] )

def login_required( f ):
    @functools.wraps( f )
    def wrapper( *args, **kwargs ):
        cs = args[ 0 ]
        if cs.loggedIn:
            return f( *args, **kwargs )
    return wrapper

class CodeShell( cmd.Cmd, OJMixin, Magic ):
    sessions, ws = {}, 'ws'
    topics, companies, problems, cheatsheet = {}, {}, {}, {}
    topic = pid = None
    xlimit = 0

    def __init__( self ):
        cmd.Cmd.__init__( self )
        Magic.__init__( self )
        if not os.path.exists( self.ws ):
            os.makedirs( self.ws )

    def precmd( self, line ):
        line = line.lower()
        if line.startswith( '/' ):
            line = 'find ' + ' '.join( line.split( '/' ) )
        self.xpid = self.pid
        return line

    def postcmd( self, stop, line ):
        if self.pid != self.xpid:
            self.ts = datetime.now()
        return stop

    def emptyline( self ):
        pass

    @property
    def prompt( self ):
        return self.sname + ':' + self.cwd + '> '

    def complete_all( self, keys, text, line, start, end ):
        prefix, suffixes = ' '.join( line.split()[ 1: ] ), []

        for t in sorted( keys ):
            if t.startswith( prefix ):
                i = len( prefix )
                suffixes.append( t[ i: ] )

        return [ text + s for s in suffixes ]

    @property
    def sname( self ):
        for s in self.sessions.itervalues():
            if s.active:
                return s.name
        return '~'

    @property
    def cwd( self ):
        wd = '/'
        if self.topic:
            wd += self.topic
            if self.pid:
                wd += '/%d-%s' % ( self.pid, self.problems[ self.pid ].slug )
        return wd

    @property
    def pad( self ):
        if self.pid:
            return '%s/%d.%s' % ( self.ws, self.pid, self.suffix )
        else:
            return None

    @property
    def tests( self ):
        return '%s/tests.dat' % self.ws

    def load( self, force=False ):
        if not self.topics or force:
            self.topics, self.companies = self.get_tags()
        if not self.problems or force:
            self.problems = self.get_problems()
            pl = set( self.problems.iterkeys() )

            for t, tpl in self.topics.iteritems():
                for pid in tpl[ : ]:
                    p = self.problems.get( pid )
                    if p:
                        p.topics.append( t )
                        pl.discard( pid )
                    else:
                        tpl.remove( pid )

            self.topics[ '#' ] = list( sorted( pl ) )
            map( lambda i: self.problems[ i ].topics.append( '#' ), pl )

            for c, cpl in self.companies.iteritems():
                cpl -= set( filter( lambda i : i not in self.problems, cpl ) )

    @contextlib.contextmanager
    def count( self, pl ):
        solved = failed = todo = 0
        for p in pl:
            if p.solved:
                solved += 1
            elif p.failed:
                failed += 1
            else:
                todo += 1
        yield
        if pl:
            print '%d solved %d failed %d todo' % ( solved, failed, todo )

    def list( self, pl ):
        with self.count( pl ):
            r = [ 1, 0.45, 0.3 ]
            for p in sorted( pl, key=lambda p: ( p.rate, p.pid ) ):
                if p.rate > r[ -1 ]:
                    print ''
                    r.pop()
                print '   ', p

    def top( self ):
        with self.count( self.problems.itervalues() ):
            pass

    def limit( self, limit ):
        def order( i, j ):
            p, q = self.problems[ i ], self.problems[ j ]
            return -int( p.freq - q.freq )

        def update( pd ):
            for k in pd.keys():
                pl = filter( lambda i: i not in ps, pd[ k ] )
                if pl:
                    pd[ k ] = pl
                else:
                    del pd[ k ]

        self.xlimit = limit
        if self.xlimit:
            ps = set( sorted( self.problems, order )[ limit : ] )
            for pid in ps:
                del self.problems[ pid ]
            for pd in [ self.topics, self.companies ]:
                update( pd )

    def do_login( self, unused=None ):
        self.login()
        self.load( force=True )
        self.limit( self.xlimit )
        self.topic = self.pid = None
        if self.loggedIn:
            print self.motd
            self.sessions = self.get_sessions()
            self.top()

    def complete_su( self, *args ):
        return self.complete_all( self.sessions.keys(), *args )

    @login_required
    def do_su( self, name ):
        if name not in self.sessions:
            prompt = self.magic( "Create session? (y/N)" )
            try:
                c = raw_input( prompt ).lower() in [ 'y', 'yes']
            except EOFError:
                c = False
            if c:
                self.sessions = self.create_session( name )

        s = self.sessions.get( name )
        if s and not s.active:
            self.sessions = self.activate_session( s.sid )
            self.load( force=True )
            self.limit( self.xlimit )

    def complete_chmod( self, *args ):
        return self.complete_all( self.langs, *args )

    def do_chmod( self, lang ):
        if lang in self.langs and lang != self.lang:
            self.lang = lang
            for p in self.problems.itervalues():
                p.code = ''
            self.cheatsheet.clear()
        else:
            print self.lang

    def do_ls( self, unused=None ):
        if not self.topic:
            for t in sorted( self.topics.keys() ):
                pl = self.topics[ t ]
                todo = 0
                for pid in pl:
                    if not self.problems[ pid ].solved:
                        todo += 1
                print '   ', '%3d' % todo, t
            self.top()

        elif not self.pid:
            pl = [ self.problems[ i ] for i in self.topics.get( self.topic ) ]
            self.list( pl )
        else:
            p = self.problems[ self.pid ]
            if not p.loaded:
                self.get_problem( p )
            if p.tags:
                print '[%s]' % p.tags
            print p.desc

    def do_find( self, key ):
        if key:
            if key in self.companies:
                fn = lambda p: p.pid in self.companies[ key ]
            else:
                fn = lambda p: p.slug.find( key ) != -1
            pl = filter( fn, self.problems.itervalues() )
            self.list( pl )

    def complete_cd( self, *args ):
        if self.topic:
            keys = [ str( i ) for i in self.topics[ self.topic ] ]
        else:
            keys = self.topics.keys()
        return self.complete_all( keys, *args )

    def do_cd( self, arg ):
        if arg == '..':
            if self.pid:
                self.pid = None
            elif self.topic:
                self.topic = None
        elif arg in self.topics:
            self.topic = arg
        elif arg.isdigit():
            pid = int( arg )
            if pid in self.problems:
                self.pid = pid
                topics = self.problems[ pid ].topics
                if self.topic not in topics:
                    self.topic = topics[ 0 ]

    def do_cat( self, unused ):
        if self.pad and os.path.isfile( self.tests ):
            with open( self.tests, 'r' ) as f:
                tests = f.read()
            print self.pad, '<<', ', '.join( tests.splitlines() )

    def do_pull( self, arg ):
        sync = arg is '*'
        def writable( p ):
            if sync:
                w = p.solved
            elif not os.path.isfile( self.pad ):
                w = True
            else:
                prompt = self.magic( "Replace working copy? (y/N)" )
                try:
                    w = raw_input( prompt ).lower() in [ 'y', 'yes']
                except EOFError:
                    w = False
            return w

        pl, xpid = sorted( self.problems ) if sync else [ self.pid ], self.pid
        for pid in pl:
            p = self.problems.get( pid )
            if p:
                if not p.loaded:
                    self.get_problem( p )

                if writable( p ):
                    self.pid = pid
                    with open( self.pad, 'w' ) as f:
                        f.write( p.code )
                    print self.pad

                with open( self.tests, 'w' ) as f:
                    f.write( p.test )
        self.pid, self.ts = xpid, datetime.now()

    @login_required
    def do_check( self, unused ):
        p = self.problems.get( self.pid )
        if p and os.path.isfile( self.pad ):
            with open( self.pad, 'r' ) as f:
                code = f.read()
                with open( self.tests, 'r' ) as tf:
                    tests = tf.read()
                    result = self.test_solution( p, code, tests )
                    if result:
                        print 'Input: ', ', '.join( tests.splitlines() )
                        print result

    @login_required
    def do_push( self, unused ):
        def histogram( t, times, limit=25 ):
            try:
                from ascii_graph import Pyasciigraph

                for i in xrange( len( times ) ):
                    t1, n = times[ i ]
                    if t1 >= t:
                        times[ i ] = ( str( t ) + '*', n )
                        break

                g = Pyasciigraph( graphsymbol='*' )
                for l in g.graph( 'Runtime' + 66 * ' ' + 'N  ms', times[ :limit ] ):
                    print l
            except ImportError:
                pass

        p = self.problems.get( self.pid )
        if p and os.path.isfile( self.pad ):
            with open( self.pad, 'r' ) as f:
                code = f.read()
                result = self.test_solution( p, code, full=True )
                if result:
                    p.solved, xsolved = result.success, p.solved
                    if p.solved:
                        runtimes = self.get_solution_runtimes( result.sid )
                        histogram( result.runtime, runtimes )
                        if not xsolved:
                            result.fintime = ( datetime.now() - self.ts ).seconds
                        status = 'Accepted'
                    else:
                        with open( self.tests, 'a+' ) as f:
                            if f.read().find( result.input ) == -1:
                                f.write( '\n' + result.input )
                        status = 'Wrong Answer'
                    p.record.add( sid=result.sid, lang=self.lang, status=status )
                    print result

    @login_required
    def do_cheat( self, limit ):
        p = self.problems.get( self.pid )
        if p:
            sid = p.record.sid
            cs = self.cheatsheet.get( p.pid, [] )
            if not cs and sid:
                cs = self.get_solutions( p.pid, sid )
                self.cheatsheet[ p.pid ] = cs

            limit = 1 if not limit else int( limit )
            for c in cs[ : limit ]:
                print c

    def do_print( self, key ):
        def order( p, q ):
            a = ( p.rate, p.pid )
            b = ( q.rate, q.pid )
            return 1 if a > b else -1 if a < b else 0

        def find( key ):
            if key in self.topics:
                topics = { key: self.topics[ key ] }
            elif key in self.companies:
                topics = { key: self.companies[ key ] }
            else:
                topics = self.topics
            return topics

        def load( pids, x ):
            pl = []
            for i in pids:
                p = self.problems[ i ]
                if not p.loaded:
                    self.get_problem( p )
                    x += 1
                    sys.stdout.write( '\r%d' % x )
                    sys.stdout.flush()
                pl.append( p )
            return pl

        def fname( key ):
            l = [ self.sname, str( self.xlimit), key ]
            l = filter( lambda w: w and w not in ( '0', '#' ), l )
            return '-'.join( l ) or 'all'

        topics, printed = find( key ), set()

        with open( self.ws + '/%s.html' % fname( key ), 'w' ) as f:
            f.write( Html.header() )
            for t, pids in sorted( topics.iteritems() ):
                pl = load( pids, len( printed ) )
                for p in sorted( pl, order ):
                    if p.pid not in printed:
                        f.write( str( Html( p ) ) )
                        printed.add( p.pid )
            f.write( Html.tail() )

    def do_clear( self, unused ):
        os.system( 'clear' )

    def do_limit( self, limit ):
        if limit.isdigit():
            limit = int( limit )
            if limit > self.xlimit > 0 or self.xlimit > limit == 0:
                self.load( force=True )
            self.limit( limit )
        elif self.xlimit:
            print self.xlimit

    def do_eof( self, arg ):
        return True

if __name__ == '__main__':
    shell = CodeShell()
    shell.do_login()
    shell.cmdloop()
