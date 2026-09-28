import html
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mirror_site', ROOT / 'tools/mirror_site.py')
mirror = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirror)


class Attributes(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.values = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.values.extend((tag, name, value) for name, value in attrs if value is not None)


class MirrorRegressionTests(unittest.TestCase):
    def test_escaped_component_url_delimiters_are_preserved(self):
        urls = ['https://definitions.sqspcdn.com/component/styles.css',
                'https://definitions.sqspcdn.com/component/visitor.js']
        for quote in ['&quot;', '&#34;', '&#x22;', '&#0034;']:
            with self.subTest(quote=quote):
                source = '<div data-block-scripts="[' + ','.join(quote + url + quote for url in urls) + ']"></div>'
                self.assertEqual(mirror.discover_absolute(source, mirror.SOURCE), set(urls))
                result = mirror.rewrite_urls(source, mirror.SOURCE, set(urls))
                self.assertEqual(json.loads(Attributes(result).values[0][2]),
                                 [mirror.local_public_url(url) for url in urls])

    def test_escaped_background_metadata_remains_valid_json(self):
        url = 'https://images.squarespace-cdn.com/image.png?format=1500w&quality=90'
        source = '<section data-current-styles="' + html.escape(json.dumps({'backgroundImage': {'assetUrl': url}}), quote=True) + '"></section>'
        self.assertEqual(mirror.discover_absolute(source, mirror.SOURCE), {url})
        result = mirror.rewrite_urls(source, mirror.SOURCE, {url})
        self.assertEqual(json.loads(Attributes(result).values[0][2])['backgroundImage']['assetUrl'], mirror.local_public_url(url))

    def test_global_lookup_does_not_require_eval(self):
        source = 'const a=Function("return this")(); const b=new Function("return this")();'
        self.assertEqual(mirror.rewrite_urls(source, mirror.SOURCE, set()),
                         'const a=globalThis; const b=globalThis;')

    def test_required_lazy_chunks_are_discovered(self):
        bundle = ('a.u=e=>"scripts/"+({1970:"background-image-fx-parallax",9528:"floating-cart",111:"unused"}[e]||e)+"."+'
                  '{8706:"one",1546:"two",1970:"three",9528:"four",111:"five"}[e]+".js";'
                  'BackgroundImageFXParallax:async()=>await Promise.all([n.e(8706),n.e(1546),n.e(1970)]).then(n.bind(n,1))')
        base = 'https://static1.squarespace.com/template/scripts/site-bundle.abc.js'
        expected = {'8706.one.js', '1546.two.js', 'background-image-fx-parallax.three.js', 'floating-cart.four.js'}
        self.assertEqual(mirror.discover_template_chunks(bundle, base, {'BackgroundImageFXParallax'}),
                         {'https://static1.squarespace.com/template/scripts/' + path for path in expected})

    def test_template_root_and_patched_vendor_use_local_urls(self):
        source = '{"templateScriptsRootUrl":"https://static1.squarespace.com/static/vta/test/scripts/"}'
        self.assertEqual(json.loads(mirror.rewrite_urls(source, mirror.SOURCE, set()))['templateScriptsRootUrl'],
                         '/_mirror/static1.squarespace.com/static/vta/test/scripts/')
        vendor = 'https://assets.squarespace.com/common-vendors-stable-abc.js'
        self.assertIn('?self-hosted=1', mirror.local_public_url(vendor))

    def test_checked_in_configuration_is_valid_and_assets_exist(self):
        count = 0
        for tag, name, value in Attributes((ROOT / 'index.html').read_text()).values:
            if not name.startswith('data-') or not value.lstrip().startswith(('{', '[')):
                continue
            with self.subTest(tag=tag, attribute=name, beginning=value[:60]):
                parsed = json.loads(value)
                count += 1
                if name in {'data-block-scripts', 'data-block-css'}:
                    for url in parsed:
                        self.assertTrue(url.startswith('/_mirror/'))
                        self.assertTrue((ROOT / urlsplit(url).path.lstrip('/')).is_file(), url)
        self.assertGreater(count, 70)

    def test_checked_in_vendor_is_csp_compatible(self):
        vendor = next((ROOT / '_mirror/assets.squarespace.com/universal/scripts-compressed').glob('common-vendors-stable-*.js'))
        self.assertNotIn('Function("return this")()', vendor.read_text())
        page = (ROOT / 'index.html').read_text()
        self.assertIn("connect-src 'none'", page)
        self.assertNotIn("'unsafe-eval'", page)

    def test_checked_in_lazy_chunks_exist(self):
        bundle = next((ROOT / '_mirror/static1.squarespace.com').rglob('site-bundle*.js'))
        url = 'https://' + str(bundle.relative_to(ROOT / '_mirror'))
        dependencies = mirror.discover_template_chunks(bundle.read_text(), url, {'BackgroundImageFXParallax'})
        self.assertGreaterEqual(len(dependencies), 4)
        for dependency in dependencies:
            self.assertTrue((ROOT / mirror.local_relative_path(dependency)).is_file(), dependency)


if __name__ == '__main__':
    unittest.main()
