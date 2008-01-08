# TODO: rewrite!

def fetched_torrent(feed, releases):
    """Mail info about new torrents"""

    email = "user@host.tld"

    subject = "New releases from %s" % feed
    mailcmd = "mail -s '%s' %s" % (subject, email)
    f = os.popen(mailcmd, 'w')
    for release in releases:
        f.write("%s\n" % release.encode('iso8859-1', 'ignore'))
    f.close()
