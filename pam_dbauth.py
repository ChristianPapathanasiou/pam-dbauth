# vim: noai:ts=2:sw=2:set expandtab:
#
# pam_dbauth.py
# Performs salted-hash authentication from a database
#
"""
  Author: Eric Windisch <eric@windisch.us>
  Copyright: 2010, Eric Windisch <eric@grokthis.net>, VPS Village
  License: EPL v1.0
"""


"""
Add to PAM configuration with:
  auth    required    pam_python.so pam_dbauth.py


Requires configuration file, /etc/security/pam_dbauth.conf,
Example:

  [database]
  host=localhost
  user=myuser
  password=mypass
  db=myuser_db
  port=XXXX
  engine=mysqldb
  ; engine=psycopg2
  ; engine=redis

  [query]
  ; SQL Example
  select_statement=select password from users where username=%s

  ; Redis example:
  ; select_statement=users:%s:password

  ; ---------------------------------------------------------------- 
  ;  Support forcing or defaulting hashtypes,
  ;  ONLY effective if stored password does not start with {hashtype}.
  ; ---------------------------------------------------------------- 
  ; hashtype_force=sha1
  ;
  ; ----------------------------------------------------------------
  ;  Default type to be used if all auto-detection fails (unlikely)
  ; ----------------------------------------------------------------
  ; hashtype_default=md5
  ;
"""

import syslog
import hashlib
import base64
import string
import sys

import ConfigParser

config = ConfigParser.ConfigParser()
config.read('/etc/security/pam_dbauth.conf')

dbengine=config.get('database','engine')
if dbengine == 'mysqldb':
  import MySQLdb
  dbengineClass=MySQLdb
elif dbengine == 'pyscopg2':
  import psycopg2
  dbengineClass=psycopg2
elif dbengine == 'redis':
  import redis
  dbengineClass=redis
else:
  syslog.syslog ("pam_dbauth.py - Unknown or unspecified database engine")
  sys.exit(1)

def pam_sm_authenticate(pamh, flags, argv):
  resp=pamh.conversation(
    pamh.Message(pamh.PAM_PROMPT_ECHO_OFF,"Password")
  )

  try:
    user = pamh.get_user(None)
  except pamh.exception, e:
    return e.pam_result
  if user == None:
    return pamh.PAM_USER_UNKNOWN

  try:
    def safeConfigGet(sect,key):
      if config.has_option(sect,key):
        return config.get(sect,key)
      else:
        None

    connargs={
      # Each engine has its own connection string type.
      # perhaps I might abstract this further into a class,
      # but for now, this module is light enough, that I 
      # simply won't bother.
      'mysqldb': { 
        'host': safeConfigGet('database','host'),
        'user': safeConfigGet('database','user'),
        'passwd': safeConfigGet('database','password'),
        'port': safeConfigGet('database','port'),
        'db': safeConfigGet('database','db')
      },
      'pyscopg2': {
        'host': safeConfigGet('database','host'),
        'user': safeConfigGet('database','user'),
        'password': safeConfigGet('database','password'),
        'port': safeConfigGet('database','port'),
        'db': safeConfigGet('database','db')
      },
      'redis': {
        'host': safeConfigGet('database','host'),
        'password': safeConfigGet('database','password'),
        'port': safeConfigGet('database','port'),
        'db': safeConfigGet('database','db')
      } 
    }[dbengine]

    # Filter out None vars.
    for k in connargs.keys():
      if connargs[k] is None:
        del connargs[k]

    # Connect to database... finally!
    db=dbengineClass.connect( **connargs )

    # Query the DB.
    # All but Redis (so-far) are SQL-based...
    if dbengine != 'redis':
      cursor=db.cursor()
      cursor.execute(config.get('query','select_statement'),(user))
      pass_raw=cursor.fetchone()[0]
    else:
      pass_raw=db.get(config.get('query','select_statement' % (user)))

    # Initalize pass_stored to pass_raw... we might change it
    pass_stored=pass_raw

    # We search for a {} section containing the hashtype
    htindex=string.find(pass_raw,"}")
    if htindex > 0:
      # password contained a hashtype
      hashtype=pass_raw[1:htindex]
      # Remove the hashtype indicator
      pass_stored=pass_raw[htindex:]
    elif config.has_option('query','hashtype_force'):
      # if a hashtype is forced on us
      hashtype=config.get('query','hashtype_force')
    elif len(pass_raw) == 16:
      # assume 16-byte length is md5
      hashtype='md5'
    elif len(pass_raw) == 20:
      # assume 20-byte length is sha-1
      hashtype='ssha2'
    elif config.has_option('query','hashtype_default'):
      # attempt to fall back...
      hashtype=config.get('query','hashtype_default')
    else:
      return pamh.PAM_SERVICE_ERR

    pass_decoded=base64.b64decode(pass_stored)

    # Set the hashlib
    hl={
      'ssha12': hashlib.sha2(),
      'sha2': hashlib.sha2(),
      'md5':  hashlib.md5()
    }[hashtype]

    pass_base=pass_decoded[:hl.digest_size]
    pass_salt=pass_decoded[hl.digest_size:]

    hl.update(resp.resp)
    hl.update(pass_salt)

    hashedrep = base64.b64encode(hl.digest())

    if hl.digest() == pass_base:
      syslog.syslog ("pam-dbauth.py hashes match")
      return pamh.PAM_SUCCESS
    else:
       pamh.PAM_AUTH_ERR
  except:
    syslog.syslog ("pam-dbauth.py exception triggered")
    return pamh.PAM_SERVICE_ERR

  return pamh.PAM_SERVICE_ERR

def pam_sm_setcred(pamh, flags, argv):
  return pamh.PAM_SUCCESS

def pam_sm_acct_mgmt(pamh, flags, argv):
  return pamh.PAM_SUCCESS

def pam_sm_open_session(pamh, flags, argv):
  return pamh.PAM_SUCCESS

def pam_sm_close_session(pamh, flags, argv):
  return pamh.PAM_SUCCESS

def pam_sm_chauthtok(pamh, flags, argv):
  return pamh.PAM_SUCCESS

#if __name__ == '__main__':
#  pam_sm_authenticate(pamh, flags, argv):


"""ff
  Author: Eric Windisch <eric@ffwindisch.us>
  Copyright: 2fffff010, Eric Windisch <eric@grokthis.net>, VPS Village
  License: EPL v1.0
"""

