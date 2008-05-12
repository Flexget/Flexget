from pysqlite2 import dbapi2 as sqlite
import sys, os.path

class Statistics:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0

    def register(self, manager, parser):
        manager.register(instance=self, event='input', keyword='stats', callback=self.input, order=65535)
        manager.register(instance=self, event='exit', keyword='stats', callback=self.exit)

    def init(self, con):
        create = """
        CREATE TABLE IF NOT EXISTS statistics
        (
           timestamp TIMESTAMP,
           feed varchar(255),
           success integer,
           failure integer
        );"""
        cur = con.cursor()
        cur.execute(create)
        con.commit()
        
    def input(self, feed):
        self.total = len(feed.entries)

    def exit(self, feed):
        self.passed = len(feed.entries)
        self.failed = self.total - self.passed

        dbname = os.path.join(sys.path[0], feed.manager.configname+".db")
        con = sqlite.connect(dbname)
        self.init(con)
        cur = con.cursor()

        cur.execute("insert into statistics (timestamp, feed, success, failure) values (date('now'), '%s', %d, %d);" % (feed.name, self.passed, self.failed))

        con.commit()
        con.close()
