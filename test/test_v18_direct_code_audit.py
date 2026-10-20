"""Independent direct Git code auditor regression tests (stdlib only)."""
import ast,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from v18_direct_code_audit import evaluate,words,target,REVIEWED

class DirectCodeAuditTests(unittest.TestCase):
    def test_words_exclude_generic_source(self):
        self.assertIn("fencing",words("Verified source fencing after restart"))
        self.assertNotIn("source",words("source fencing"))
    def test_ast_target(self):
        self.assertEqual(target(ast.parse("obj.run_work()").body[0].value.func),"run_work")
    def test_no_source_is_never_promotion(self):
        row=evaluate({"id":"CA-9999","kind":"Build","requirement":"Fenced independent restoration"},[],{},{},{})
        self.assertEqual(row["status"],"UNVERIFIED")
        self.assertEqual(row["source_trace"],"no_source_symbol_link")
        self.assertFalse(row["promoted"])
    def test_relevant_code_caller_remains_unverified(self):
        words_in=words("Persistent recovery guard for orphaned worker")
        entry={"path":"src/sofia/recovery.py","line":8,"name":"recovery_guard",
               "test":False,"body":words_in,"namewords":words("recovery_guard"),
               "doc":words_in,"mentions":set(),"assertive":False}
        index={w:{0} for w in words_in}
        row=evaluate({"id":"CA-9999","kind":"Build","requirement":"Persistent recovery guard for orphaned worker"},
            [entry],index,{"recovery_guard":[("src/sofia/app.py",16)]},
            {"recovery_guard":[("test/test_recovery.py",22,"test_guard")]})
        self.assertEqual(row["source_trace"],"symbol_caller_test")
        self.assertFalse(row["promoted"])
    def test_prior_manually_reviewed_exact(self):
        self.assertEqual(len(REVIEWED),40)

if __name__=="__main__":unittest.main()
