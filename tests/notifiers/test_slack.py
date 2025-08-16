import pytest


@pytest.mark.online
class TestSlackNotifier:
    config = """
        templates:
            global:
                accept_all: yes
        tasks:
            slack:
              mock:
                  - title: title
                    tvdb_url: https://thetvdb.com/series/star-trek-picard/episodes/7550686
                    series_name: 'Star Trek: Picard'
                    series_id: S01E03
                    tvdb_ep_overview: 'Completely unaware of her special nature, Soji continues her work and captures the attention of the Borg cube research project’s executive director. After rehashing past events with a reluctant Raffi, Picard seeks others willing to join his search for Bruce Maddox, including pilot and former Starfleet officer Cristóbal Rios.'
                    imdb_score: 8.6
                    imdb_genres: [Action,Adventure,Drama,Sci-Fi]
                    imdb_mpaa_rating: TV-MA
                    imdb_actors:
                      1: Patrick Stewart
                      2: Alison Pill
                      3: Isa Briones
                      4: Harry Treadaway
                    tvdb_banner: https://artworks.thetvdb.com/banners/v4/series/364093/posters/61e846a7440f8.jpg
              notify:
                  entries:
                    via:
                      - slack:
                          web_hook_url: "https://hooks.slack.com/services/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"
                          blocks:
                            - section:
                                text: '<{{ tvdb_url }}|{{ series_name }} ({{ series_id }})>'
                            - section:
                                text: '{{ tvdb_ep_overview }}'
                                image:
                                  url: "https://api.slack.com/img/blocks/bkb_template_images/plants.png"
                                  alt_text: 'plants'
                                fields:
                                  - '*Score*'
                                  - '*Genres*'
                                  - '{{ imdb_score }}'
                                  - "{{ imdb_genres | join(', ') | title }}"
                                  - '*Rating*'
                                  - '*Cast*'
                                  - '{{ imdb_mpaa_rating }}'
                                  - >
                                    {% for key, value in imdb_actors.items() %}{{ value }}{% if not loop.last %}, {% endif %}
                                    {% endfor %}
                            - image:
                                url: "{{ tvdb_banner }}"
                                alt_text: "{{ series_name }} Banner"
                            - divider: True
                            - context:
                                - image:
                                    url: 'https://image.freepik.com/free-photo/red-drawing-pin_1156-445.jpg'
                                    alt_text: 'red pin'
                                - text: ':round_pushpin:'
                                - text: 'Task: {{ task }}'
        """  # noqa: RUF001

    def test_slack(self, execute_task):
        execute_task('slack', options={'test': True})
