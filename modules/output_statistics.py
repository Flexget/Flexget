import sys, os.path

has_sqlite = True
try:
    from pysqlite2 import dbapi2 as sqlite
except:
    has_sqlite = False

class Statistics:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0

    def register(self, manager, parser):
        manager.register(instance=self, event='input', keyword='stats', callback=self.input, order=65535)
        manager.register(instance=self, event='exit', keyword='stats', callback=self.exit)
        manager.register(instance=self, event='terminate', keyword='stats', callback=self.generate_statistics)

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
        if not has_sqlite:
            raise Exception('module statistics requires python-sqlite2 (Sqlite v3) library.')
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


    def generate_statistics(self, feed):
        sql = """
        select feed, strftime("%w", timestamp) as dow, sum(success) from statistics group by feed, dow;
        """
        dbname = os.path.join(sys.path[0], feed.manager.configname+".db")
        con = sqlite.connect(dbname)
        cur = con.cursor()
        cur.execute(sql)

        outname = os.path.join(sys.path[0], feed.manager.configname+"_statistics.txt")
        f = file(outname, 'w')
        for feed, dow, success in cur:
            f.write("%-10s %-10s %-10s\n" % (feed, dow, success))

        f.close()
