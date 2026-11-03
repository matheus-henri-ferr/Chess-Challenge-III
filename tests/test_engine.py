"""Run after building engine.exe: python tests/test_engine.py"""
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine.exe"


class EngineTests(unittest.TestCase):
    def test_special_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = pathlib.Path(directory) / "rules.exe"
            subprocess.run(["g++", "-O2", "-std=c++17", "-o", str(binary),
                            str(ROOT / "tests" / "rules.cpp"),
                            str(ROOT / "tabuleiro.cpp"), str(ROOT / "xadrez.cpp")],
                           cwd=ROOT, check=True, timeout=60)
            subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=10)

    def test_start_position_perft(self):
        run = subprocess.run([str(ENGINE), "perft", "5"], cwd=ROOT,
                             capture_output=True, text=True, check=True, timeout=60)
        for depth, nodes in enumerate((20, 400, 8902, 197281, 4865609), 1):
            self.assertIn(f"perft({depth}) = {nodes} ", run.stdout)

    def test_black_legal_input_and_log(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "partida.log"
            run = subprocess.run([str(ENGINE), "tournament", "black", str(path)],
                                 cwd=ROOT, input="e2e5\ne2e4\n0.01\nok\nsair\n",
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("Lance ilegal", run.stdout)
            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 3)
            self.assertIn("1 brancas e2e4 0 0", lines[1])
            self.assertIn("1 pretas ", lines[2])
            self.assertIn('"', lines[2])

    def test_undo_rewrites_log_and_turn(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "partida.log"
            run = subprocess.run([str(ENGINE), "tournament", "black", str(path)],
                                 cwd=ROOT, input="e2e4\ndesfazer\nd2d4\nsair\n",
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("1 brancas d2d4 ", lines[1])


if __name__ == "__main__":
    unittest.main()
