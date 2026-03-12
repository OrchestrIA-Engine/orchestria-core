import sys, os, json
sys.path.insert(0, ".")
from src.parsers.genesys_yaml_parser import GenesysYAMLParser
from src.agents.analyzer import IVRAnalyzer

api_key = os.environ.get("ANTHROPIC_API_KEY")
parser = GenesysYAMLParser()
analyzer = IVRAnalyzer(api_key=api_key)

fixtures_dir = "tests/fixtures"
casos = sorted([f for f in os.listdir(fixtures_dir) if f.endswith(".json")])
resultados = []

print("Ejecutando evaluation suite...\n")

for fixture_file in casos:
    with open(f"{fixtures_dir}/{fixture_file}") as f:
        caso = json.load(f)

    flow = parser.parse(caso["yaml"], flow_name=caso["name"])
    analysis = analyzer.analyze(flow)
    expected = caso["expected"]
    score = analysis.get("score", 0)
    critical = len(analysis.get("critical_issues", []))
    improvements = len(analysis.get("improvements", []))

    passed = True
    failures = []

    if "min_score" in expected and score < expected["min_score"]:
        passed = False
        failures.append(f"Score {score} < min {expected['min_score']}")
    if "max_score" in expected and score > expected["max_score"]:
        passed = False
        failures.append(f"Score {score} > max {expected['max_score']}")
    if "max_critical_issues" in expected and critical > expected["max_critical_issues"]:
        passed = False
        failures.append(f"Critical issues {critical} > max {expected['max_critical_issues']}")
    if "min_critical_issues" in expected and critical < expected["min_critical_issues"]:
        passed = False
        failures.append(f"Critical issues {critical} < min {expected['min_critical_issues']}")
    if "min_improvements" in expected and improvements < expected["min_improvements"]:
        passed = False
        failures.append(f"Improvements {improvements} < min {expected['min_improvements']}")

    status = "PASS" if passed else "FAIL"
    print(f"{status} | {caso['id']} | {caso['name']} | Score: {score}/100 | Issues: {critical}")
    for fail in failures:
        print(f"     -> {fail}")

    resultados.append({"id": caso["id"], "passed": passed})

total = len(resultados)
passed_count = sum(1 for r in resultados if r["passed"])
print(f"\nRESULTADO FINAL: {passed_count}/{total} tests pasaron ({passed_count/total*100:.0f}%)")
