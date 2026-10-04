import argparse
import json
import logging
import os
from pathlib import Path
from .evaluation import run_evaluations
from .server import make_server
from .service import Service


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # The offline app intentionally has no third-party dependencies.
    parser = argparse.ArgumentParser(description="Vaani sales conversation lab")
    parser.add_argument("command", choices=["serve", "evaluate"], nargs="?", default="serve")
    parser.add_argument("--db", default=os.getenv("VAANI_DB", "data/vaani.sqlite3"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--planner", choices=["rules", "gemini"], default="rules")
    parser.add_argument("--prompt", choices=["zero-shot-v1", "few-shot-v2"], default="few-shot-v2")
    parser.add_argument("--report", help="Optional JSON report output path")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    service = Service(args.db)
    if args.command == "evaluate":
        result = run_evaluations(args.planner, args.prompt)
        service.save_evaluation(result)
        if args.report:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"{result['passed']}/{result['total']} scenarios passed ({args.planner}, {args.prompt})")
        for case in result["results"]:
            if not case["passed"]:
                print(case["name"], case["errors"])
        raise SystemExit(0 if result["passed"] == result["total"] else 1)
    server = make_server(service, args.port)
    print(f"Vaani is ready at http://127.0.0.1:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
