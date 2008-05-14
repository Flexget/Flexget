import sys, os.path

has_sqlite = True
try:
    from pysqlite2 import dbapi2 as sqlite
except:
    has_sqlite = False

has_pygooglechart = True
try:
    from pygooglechart import StackedVerticalBarChart, Axis
except:
    has_pygooglechart = False

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

        cur.execute("insert into statistics (timestamp, feed, success, failure) values (datetime('now'), '%s', %d, %d);" % (feed.name, self.passed, self.failed))

        con.commit()
        con.close()

    def generate_statistics(self, feed):
        if not has_pygooglechart:
            raise Exception('module statistics requires pygooglechart library.')
        
        dbname = os.path.join(sys.path[0], feed.manager.configname+".db")
        con = sqlite.connect(dbname)

        self.weekly_stats(feed, con)
        self.hourly_stats(feed, con)

    def hourly_stats(self, feed, con):
        sql = """
        select strftime("%H", timestamp, 'localtime') as hour, sum(success) from statistics group by hour
        """
        cur = con.cursor()
        cur.execute(sql)

        chart = StackedVerticalBarChart(660, 100, title="Releases by hour")
        axislabels = [str(i) for i in range(24)]
        data = 24*[0]
            
        axis = chart.set_axis_labels(Axis.BOTTOM, axislabels)
        chart.set_axis_style(axis, '000000', alignment=-1)

        for hour, success in cur:
            hour = int(hour)

            data[hour] = success

        chart.add_data(data)

        chartname = os.path.join(sys.path[0], feed.manager.configname + "_hourly.png")
        charthtml = os.path.join(sys.path[0], feed.manager.configname + "_hourly.html")

        chart.download(chartname)
        url = chart.get_url()
        f = file(charthtml, 'w')
        f.write(url)
        f.close()

    def weekly_stats(self, feed, con):
        sql = """
        select strftime("%w", timestamp, 'localtime') as dow, sum(success) from statistics group by dow
        """

        cur = con.cursor()
        cur.execute(sql)

        chart = StackedVerticalBarChart(200, 100, title="Releases by day of week")
        axis = chart.set_axis_labels(Axis.BOTTOM, ['mon','tue','wed','thu','fri','sat','sun'])
        chart.set_axis_style(axis, '000000', alignment=-1)

        data = 7*[0]

        for dow, success in cur:
            dow = int(dow) - 1
            if dow == -1:
                dow = 6

            data[dow] = success

        chart.add_data(data)

        chartname = os.path.join(sys.path[0], feed.manager.configname + "_weekly.png")
        charthtml = os.path.join(sys.path[0], feed.manager.configname + "_weekly.html")

        chart.download(chartname)
        url = chart.get_url()
        f = file(charthtml, 'w')
        f.write(url)
        f.close()
