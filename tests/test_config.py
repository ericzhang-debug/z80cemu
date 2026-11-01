import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platform_support.config_loader import load_memory
from platform_core import Machine

class ConfigTests(unittest.TestCase):
    def read(self, specs):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'memory.json'
            path.write_text(json.dumps({'memory': specs}), encoding='utf-8')
            return load_memory(path)
    def test_numeric_formats(self):
        self.assertEqual(self.read([{'name':'x','type':'ram','start':'0x1000','size':256}])[0]['start'], 4096)
    def test_duplicate_memory_instances_are_named_separately(self):
        specs = self.read([{'name':'RAM','type':'ram','start':0,'size':256},
                           {'name':'RAM','type':'ram','start':256,'size':256}])
        machine = Machine({'memory': specs})
        self.assertEqual([device.name for device in machine.memory], ['RAM', 'RAM (2)'])
    def test_invalid_maps(self):
        for specs in ([], [{'name':'x','type':'other','start':0,'size':1}],
                      [{'name':'x','type':'ram','start':65535,'size':2}],
                      [{'name':'x','type':'rom','start':0,'size':2}, {'name':'y','type':'ram','start':1,'size':2}],
                      [{'name':'x','type':'ram','start':True,'size':1}]):
            with self.subTest(specs=specs), self.assertRaises(ValueError): self.read(specs)
    def test_interleaved_regions_and_alias(self):
        specs = [{'name':'rom', 'type':'rom', 'size':'0x200', 'regions':[
            {'start':'0x0000', 'size':'0x100', 'offset':0},
            {'start':'0x0200', 'size':'0x100', 'offset':'0x100'},
            {'start':'0x0400', 'size':'0x100', 'offset':0}]},
            {'name':'ram', 'type':'ram', 'size':'0x200', 'regions':[
            {'start':'0x0100', 'size':'0x100', 'offset':0},
            {'start':'0x0300', 'size':'0x100', 'offset':'0x100'}]}]
        machine = Machine({'memory': self.read(specs)})
        machine.memory[0].load(bytes([0xaa]) + bytes(255) + bytes([0xbb]))
        machine.write(0x100, 0x55); machine.write(0x300, 0x66)
        self.assertEqual([machine.read(i) for i in (0, 0x100, 0x200, 0x300, 0x400)], [0xaa, 0x55, 0xbb, 0x66, 0xaa])
