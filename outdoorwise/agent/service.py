import json
import httpx
from outdoorwise.contracts.models import ChatResponse,Trace
from .tools import TOOLS,ToolRegistry
SYSTEM="""You are OutdoorWise's route assistant. Use only provided tools as evidence.
The request's validated UI preferences are authoritative: do not silently replace them.
If natural-language preferences conflict with the form, explain and ask the user to update it.
Routes are candidates requiring visual review. Never claim safety or validated navigation.
Mock probabilities MUST be described as simulated; missing forecast means unknown risk.
Official WBGT and heat stress are observations, not forecasts. Check fresh/stale/missing and live/cache/demo. Unavailable risk module means no compound risk estimate. Observation rainfall is not future rain probability. Do not invent route IDs, weather or facilities.
Call rank_routes before giving a recommendation. Tools are read-only except local audit snapshots.
If a request is unclear, ask a concise question. Answer in the user's language.
"""
class AgentService:
    def __init__(self,pipeline,settings): self.pipeline=pipeline; self.settings=settings
    def chat(self,request):
        registry=ToolRegistry(self.pipeline,request.preferences); trace=[]
        if self.settings.agent_mode=='demo':
            for name in ['search_routes','get_route_conditions','get_rain_prediction','rank_routes']:
                result=registry.call(name,{})
                trace.append(Trace(tool=name,arguments={},result=result))
            run=registry.last_run
            names={r.route_id:r.name for r in run.routes}
            ranked=run.recommendations
            if ranked:
                best=ranked[0]
                message=f'Rule-based demo: based on the form preferences, the first candidate is {names[best.route_id]}. '+ ' '.join(best.reasons)
            else: message='Rule-based demo: no candidate routes satisfy the current limits. Please adjust the distance limit.'
            message+=' This demo follows a fixed tool sequence. Use the form to update your preferences.'
        else:
            messages=[{'role':'system','content':SYSTEM}, {'role':'user','content':json.dumps({
                'message':request.message,'preferences':request.preferences.model_dump(mode='json')},ensure_ascii=False)}]
            message=None
            with httpx.Client(timeout=45) as client:
                for turn in range(6):
                    response=client.post(self.settings.llm_base_url.rstrip('/')+'/chat/completions',
                      headers={'Authorization':'Bearer '+self.settings.llm_api_key},
                      json={'model':self.settings.llm_model,'messages':messages,'tools':TOOLS,
                            'tool_choice':'auto','parallel_tool_calls':False})
                    response.raise_for_status(); reply=response.json()['choices'][0]['message']
                    calls=reply.get('tool_calls') or []
                    if not calls:
                        message=reply.get('content') or 'No response.'; break
                    messages.append({k:reply[k] for k in ['role','content','tool_calls'] if k in reply})
                    for call in calls:
                        try:
                            args=json.loads(call['function']['arguments']); name=call['function']['name']
                            result=registry.call(name,args)
                            trace.append(Trace(tool=name,arguments=args,result=result))
                        except (ValueError,TypeError,KeyError): result={'error':'Invalid tool name or arguments. Use listed tools and their declared parameter schemas.'}
                        messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result,ensure_ascii=False)})
                if message is None: message='Tool-call limit reached. Please simplify your request.'
            run=registry.last_run
        # Cards are based ONLY on server-side rank_routes output, never IDs in generated prose.
        ids=[r.route_id for r in run.recommendations] if run and any(t.tool=='rank_routes' for t in trace) else []
        return ChatResponse(message=message,agent_mode=self.settings.agent_mode,trace=trace,recommended_route_ids=ids,run=run)
