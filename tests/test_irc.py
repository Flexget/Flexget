from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase

from xml.etree import ElementTree as ET

from flexget.entry import Entry
from flexget.plugins.daemon.irc import IRCConnection


class TestIRCRules(FlexGetBase):

    def run_rules(self, entry, rules):
        c = IRCConnection({'testx_1': 'testval1'}, 'test')
        return c.process_tracker_config_rules(entry, ET.fromstring("<root>%s</root>" % rules))

    def test_rule_var_simple(self):
        result = self.run_rules(
            Entry(irc_baseurl='test', irc_torrentname='test2'),
            """<var name="torrentUrl">
                    <string value="yes"/>
                </var>"""
        )
        assert result['irc_torrenturl'] == 'yes'

    def test_rule_var_no_rules(self):
        result = self.run_rules(
            Entry(irc_baseurl='test', irc_torrentname='test2'),
            """<var name="torrentUrl">
                </var>"""
        )
        assert result['irc_torrenturl'] == ''

    def test_rule_var_simple_from_config(self):
        result = self.run_rules(
            Entry(irc_baseurl='test', irc_torrentname='test2'),
            """<var name="torrentUrl">
                    <var name="testx_1"/>
                </var>"""
        )
        assert result['irc_torrenturl'] == 'testval1'

    def test_rule_var_simple_varenc(self):
        result = self.run_rules(
            Entry(irc_baseurl='test', irc_torrentname='test2', irc_test1='t o'),
            """<var name="torrentUrl">
                    <varenc name="test1"/>
                </var>"""
        )
        assert result['irc_torrenturl'] == 't%20o'

    def test_rule_var_concat(self):
        result = self.run_rules(
            Entry(irc_baseurl='test', irc_torrentname='test 2'),
            """<var name="torrentUrl">
                    <string value="http://"/>
                    <var name="baseUrl"/>
                    <string value="/rssdownload.php/"/>
                    <varenc name="torrentName"/>
                </var>"""
        )
        assert result['irc_torrenturl'] == 'http://test/rssdownload.php/test%202'

    def test_rule_var_invalid_source(self):
        result = self.run_rules(
            Entry(irc_baseurl='test', irc_torrentname='test2'),
            """<var name="torrentUrl">
                    <string value="http://"/>
                    <var name="baseUrlx"/>
                    <string value="/rssdownload.php/"/>
                    <varenc name="torrentName"/>
                </var>"""
        )
        assert 'irc_torrenturl' not in result

    def test_rule_var_invalid_operation(self):
        result = self.run_rules(
            Entry(irc_baseurl='test', irc_torrentname='test2'),
            """<var name="torrentUrl">
                    <varxxxx name="baseUrl"/>
                </var>"""
        )
        assert 'irc_torrenturl' not in result

    def test_rule_varreplace_basic(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<varreplace name="torrentUrl" srcvar="baseurl" regex="llama" replace=" "/>"""
        )
        assert 'irc_torrenturl' in result
        assert result['irc_torrenturl'] == u' test'

    def test_rule_varreplace_empty_regex(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<varreplace name="torrentUrl" srcvar="baseurl" regex="" replace=""/>"""
        )
        assert 'irc_torrenturl' in result
        assert result['irc_torrenturl'] == u'llamatest'

    def test_rule_varreplace_invalid(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<varreplace name="torrentUrl" src="baseurl" regex="" replace=""/>"""
        )
        assert 'irc_torrenturl' not in result

    def test_rule_varreplace_invalid_missing_option(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<varreplace name="torrentUrl" srcvar="baseurl" regex=""/>"""
        )
        assert 'irc_torrenturl' not in result

    def test_rule_if_matching(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<if srcvar="baseurl" regex="llamatest">
                 <varreplace name="torrentUrl" srcvar="torrentname" regex="2" replace="x"/>
               </if>"""
        )
        assert 'irc_torrenturl' in result
        assert result['irc_torrenturl'] == 'testx'

    def test_rule_if_not_matching(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<if srcvar="baseurl" regex="llt">
                 <varreplace name="torrentUrl" srcvar="torrentname" regex="2" replace="x"/>
               </if>"""
        )
        assert 'irc_torrenturl' not in result

    def test_rule_if_missing_option(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<if srcvar="baseurl">
                 <varreplace name="torrentUrl" srcvar="torrentname" regex="2" replace="x"/>
               </if>"""
        )
        assert 'irc_torrenturl' not in result

    def test_rule_extract(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<extract srcvar="baseurl">
                 <regex value="ll(a)m(a)"/>
                 <vars>
                   <var name="t1"/>
                   <var name="t2"/>
                 </vars>
               </extract>"""
        )
        assert 'irc_t1' in result
        assert 'irc_t2' in result
        assert result['irc_t1'] == 'a'
        assert result['irc_t2'] == 'a'

    def test_rule_extract_not_matching(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<extract srcvar="baseurl">
                 <regex value="kl(a)m(a)"/>
                 <vars>
                   <var name="t1"/>
                   <var name="t2"/>
                 </vars>
               </extract>"""
        )
        assert 'irc_t1' not in result
        assert 'irc_t2' not in result

    def test_rule_extract_invalid_missing_regex(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<extract srcvar="baseurl">
                 <vars>
                   <var name="t1"/>
                   <var name="t2"/>
                 </vars>
               </extract>"""
        )
        assert 'irc_t1' not in result
        assert 'irc_t2' not in result

    def test_rule_extract_incorrect_var(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<extract srcvar="baseurl">
                 <regex value="ll(a)m(a)"/>
                 <vars>
                   <varxx name="t1"/>
                   <var name="t2"/>
                 </vars>
               </extract>"""
        )
        assert 'irc_t1' not in result
        assert 'irc_t2' in result
        assert result['irc_t2'] == 'a'

    def test_rule_setregex(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<setregex srcvar="baseurl" regex="ll(a)m(a)" varName="t1" newValue="1"/>"""
        )
        assert 'irc_t1' in result
        assert result['irc_t1'] == '1'

    def test_rule_setregex_no_match(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<setregex srcvar="baseurl" regex="xll(a)m(a)" varName="t1" newValue="1"/>"""
        )
        assert 'irc_t1' not in result

    def test_rule_setregex_missing_regex(self):
        result = self.run_rules(
            Entry(irc_baseurl='llamatest', irc_torrentname='test2'),
            """<setregex srcvar="baseurl" varName="t1" newValue="1"/>"""
        )
        assert 'irc_t1' not in result

    def test_rule_extracttags(self):
        result = self.run_rules(
            Entry(irc_tags='MP4 , SD  , x264  , P2P , DSR'),
            """<extracttags srcvar="tags" split=",">
                <setvarif varName="origin" regex="^(?:None|Scene|P2P|Internal|User|Mixed)$"/>

                <setvarif varName="resolution" regex="^(?:SD|Standard?Def.*|480i|480p|576p|720p|810p|1080p|1080i|PD|Portable Device)$"/>
                <setvarif varName="source" regex="^(?:R5|DVDScr|BRRip|CAM|TS|TELESYNC|TC|TELECINE|DSR|PDTV|HDTV|DVDRip|BDRip|DVDR|DVD|BluRay|Blu\-Ray|WEBRip|WEB\-DL|WEB|TVRip|HDDVD|HD\-DVD)$"/>
                <setvarif varName="encoder" regex="^(?:XviD|DivX|x264|x264\-Hi10p|h\.264|h264|mpeg2|VC\-1|VC1|WMV)$"/>

                <setvarif varName="container" regex="^(?:AVI|MKV|VOB|MPEG|MP4|ISO|WMV|TS|M4V|M2TS)$"/>

                <!--Ignored-->
                <regex value=""/>
            </extracttags>"""
        )

        assert 'irc_origin' in result
        assert 'irc_resolution' in result
        assert 'irc_source' in result
        assert 'irc_encoder' in result
        assert 'irc_container' in result
        assert result['irc_origin'] == 'P2P'
        assert result['irc_resolution'] == 'SD'
        assert result['irc_source'] == 'DSR'
        assert result['irc_encoder'] == 'x264'
        assert result['irc_container'] == 'MP4'

    def test_rule_extracttags_partial_matches(self):
        result = self.run_rules(
            Entry(irc_tags='MP4 , x264  , P2P '),
            """<extracttags srcvar="tags" split=",">
                <setvarif varName="origin" regex="^(?:None|Scene|P2P|Internal|User|Mixed)$"/>

                <setvarif varName="resolution" regex="^(?:SD|Standard?Def.*|480i|480p|576p|720p|810p|1080p|1080i|PD|Portable Device)$"/>
                <setvarif varName="source" regex="^(?:R5|DVDScr|BRRip|CAM|TS|TELESYNC|TC|TELECINE|DSR|PDTV|HDTV|DVDRip|BDRip|DVDR|DVD|BluRay|Blu\-Ray|WEBRip|WEB\-DL|WEB|TVRip|HDDVD|HD\-DVD)$"/>
                <setvarif varName="encoder" regex="^(?:XviD|DivX|x264|x264\-Hi10p|h\.264|h264|mpeg2|VC\-1|VC1|WMV)$"/>

                <setvarif varName="container" regex="^(?:AVI|MKV|VOB|MPEG|MP4|ISO|WMV|TS|M4V|M2TS)$"/>

                <!--Ignored-->
                <regex value=""/>
            </extracttags>"""
        )

        assert 'irc_origin' in result
        assert 'irc_encoder' in result
        assert 'irc_container' in result
        assert 'irc_resolution' not in result
        assert 'irc_source' not in result
        assert result['irc_origin'] == 'P2P'
        assert result['irc_encoder'] == 'x264'
        assert result['irc_container'] == 'MP4'

    def test_rule_extracttags_invalid_varname_setvarif(self):
        result = self.run_rules(
            Entry(irc_tags='MP4 , SD  , x264  , P2P , DSR'),
            """<extracttags srcvar="tags" split=",">
                <setvarif varName="origin" regex="^(?:None|Scene|P2P|Internal|User|Mixed)$"/>

                <setvarif regex="^(?:SD|Standard?Def.*|480i|480p|576p|720p|810p|1080p|1080i|PD|Portable Device)$"/>
                <setvarif varName="source" regex="^(?:R5|DVDScr|BRRip|CAM|TS|TELESYNC|TC|TELECINE|DSR|PDTV|HDTV|DVDRip|BDRip|DVDR|DVD|BluRay|Blu\-Ray|WEBRip|WEB\-DL|WEB|TVRip|HDDVD|HD\-DVD)$"/>
                <setvarif varName="encoder" regex="^(?:XviD|DivX|x264|x264\-Hi10p|h\.264|h264|mpeg2|VC\-1|VC1|WMV)$"/>

                <setvarif varName="container" regex="^(?:AVI|MKV|VOB|MPEG|MP4|ISO|WMV|TS|M4V|M2TS)$"/>

                <!--Ignored-->
                <regex value=""/>
            </extracttags>"""
        )

        assert 'irc_origin' in result
        assert 'irc_resolution' not in result
        assert 'irc_source' in result
        assert 'irc_encoder' in result
        assert 'irc_container' in result
        assert result['irc_origin'] == 'P2P'
        assert result['irc_source'] == 'DSR'
        assert result['irc_encoder'] == 'x264'
        assert result['irc_container'] == 'MP4'

    def test_rule_extracttags_invalid_regex_setvarif(self):
        result = self.run_rules(
            Entry(irc_tags='MP4 , SD  , x264  , P2P , DSR'),
            """<extracttags srcvar="tags" split=",">
                <setvarif varName="origin" regex="^(?:None|Scene|P2P|Internal|User|Mixed)$"/>

                <setvarif varName="resolution"/>
                <setvarif varName="source" regex="^(?:R5|DVDScr|BRRip|CAM|TS|TELESYNC|TC|TELECINE|DSR|PDTV|HDTV|DVDRip|BDRip|DVDR|DVD|BluRay|Blu\-Ray|WEBRip|WEB\-DL|WEB|TVRip|HDDVD|HD\-DVD)$"/>
                <setvarif varName="encoder" regex="^(?:XviD|DivX|x264|x264\-Hi10p|h\.264|h264|mpeg2|VC\-1|VC1|WMV)$"/>

                <setvarif varName="container" regex="^(?:AVI|MKV|VOB|MPEG|MP4|ISO|WMV|TS|M4V|M2TS)$"/>

                <!--Ignored-->
                <regex value=""/>
            </extracttags>"""
        )

        assert 'irc_origin' in result
        assert 'irc_resolution' not in result
        assert 'irc_source' in result
        assert 'irc_encoder' in result
        assert 'irc_container' in result
        assert result['irc_origin'] == 'P2P'
        assert result['irc_source'] == 'DSR'
        assert result['irc_encoder'] == 'x264'
        assert result['irc_container'] == 'MP4'