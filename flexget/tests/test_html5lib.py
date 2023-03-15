from flexget.utils.soup import get_soup


class TestHtml5Lib:
    config = 'tasks: {}'

    def test_parse_broken(self, execute_task):
        s = """<html>
<head><title>Foo</title>
<body>
<p class=foo><b>Some Text</b>
<p><em>Some Other Text</em>"""
        soup = get_soup(s)

        body = soup.find('body')
        ps = body.find_all('p')
        assert ps[0].parent.name == 'body'
        assert ps[1].parent.name == 'body'
        b = soup.find('b')
        assert b.parent.name == 'p'
        em = soup.find('em')
        assert em.parent.name == 'p'

        assert soup.find('p', attrs={'class': 'foo'})
