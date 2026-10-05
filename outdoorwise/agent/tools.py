"""Validated tool registry; no arbitrary function dispatch."""
from outdoorwise.contracts.models import Preferences
TOOLS=[{'type':'function','function':{'name':name,'description':description,
    'parameters':{'type':'object','properties':{},'required':[],'additionalProperties':False}}}
    for name,description in [
      ('search_routes','List all curated routes, lengths and review status.'),
      ('get_route_conditions','Get observations, freshness, provenance and official heat stress; not forecasts.'),
      ('get_route_environment','Read structured environments for all curated routes; does not fetch APIs.'),
      ('get_rain_prediction','Get predictions for UI-selected horizon; check mock and unavailable labels.'),
      ('rank_routes','Run pipeline using UI preferences; return ranked routes and warnings.')]]
for tool in TOOLS:
    if tool['function']['name']=='get_route_environment':
        tool['function']['parameters']={'type':'object','properties':{'route_id':{'type':'string'},'as_of':{'type':'string','description':'ISO8601 timezone-aware time; omit for current'}},'required':['route_id'],'additionalProperties':False}
class ToolRegistry:
    def __init__(self,pipeline,preferences: Preferences):
        self.pipeline=pipeline; self.preferences=preferences; self.last_run=None
    def call(self,name,arguments):
        if name not in {t['function']['name'] for t in TOOLS}: raise ValueError('Unknown tool')
        if name=='get_route_environment':
            if set(arguments)-{'route_id','as_of'} or not isinstance(arguments.get('route_id'),str):raise ValueError('route_id required')
            from outdoorwise.contracts.environment import timestamp
            return {'environment':self.pipeline.get_route_environment(arguments['route_id'],timestamp(arguments['as_of']) if arguments.get('as_of') else None).model_dump(mode='json')}
        if arguments: raise ValueError('These v1 tools take no arguments; preferences come from the request form')
        if name=='search_routes':
            return {'routes':[r.model_dump(mode='json',exclude={'geometry'}) for r in self.pipeline.repository.load_routes()]}
        if self.last_run is None or name=='rank_routes': self.last_run=self.pipeline.run(self.preferences)
        key={'get_route_conditions':'environment','get_route_environment':'environment','get_rain_prediction':'predictions','rank_routes':'recommendations'}[name]
        return {key:[x.model_dump(mode='json') for x in getattr(self.last_run,key)],'risks':[x.model_dump(mode='json') for x in self.last_run.risks],'warnings':self.last_run.warnings}
