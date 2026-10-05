import argparse,json
from .config import Settings
from .bootstrap import build_pipeline
from .contracts.models import Preferences
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['collect','run','schemas'])
    parser.add_argument('--horizon',type=int,choices=[30,60],default=30); parser.add_argument('--due',action='store_true'); args=parser.parse_args()
    if args.command=='schemas':
        from .contracts import environment, models
        print(json.dumps({name:obj.model_json_schema() for name in ['Observation','Conditions','Prediction','Preferences','Run','ChatResponse'] if (obj:=getattr(models,name))},indent=2)); return
    pipeline=build_pipeline(Settings.from_env())
    if args.command=='collect': print(json.dumps(pipeline.refresh(due_only=args.due)))
    else: print(pipeline.run(Preferences(horizon_min=args.horizon)).model_dump_json(indent=2))
if __name__=='__main__': main()
