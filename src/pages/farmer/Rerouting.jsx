import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { GitBranch, Clock, ShieldCheck, Factory, ArrowRight } from 'lucide-react';
import { useStore } from '../../hooks/useStore';
import { agriRouteApi } from '../../api/agriRoute';
import { remaining } from '../../data/mock';
import { PageHeader, Badge, EmptyState } from '../../components/UI';

export default function Rerouting() {
  const { produce, routingCases, advance, loading, loadError } = useStore();
  const [id, setId] = useState('');
  const batch = produce.find(item => item.id === id) ?? produce.find(item => item.eligible && remaining(item) > 0) ?? produce[0];
  const [readiness, setReadiness] = useState(null);
  const [error, setError] = useState('');
  const activeCase = batch && routingCases.find(item => item.produce_batch_id === batch.apiId);

  useEffect(() => {
    if (!batch?.apiId) { setReadiness(null); return; }
    let active = true;
    agriRouteApi.routingReadiness(batch.apiId).then(value => { if (active) { setReadiness(value); setError(''); } })
      .catch(reason => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [batch?.apiId, produce]);

  if (loading) return <section className="panel"><p className="muted">Loading routing readiness…</p></section>;
  if (loadError) return <section className="panel"><p role="alert">{loadError}</p></section>;
  if (!batch) return <><PageHeader title="Dynamic Produce Routing" description="Record matching attempts and review backend-calculated routing readiness."/><EmptyState title="No produce batches available" description="Add produce before checking routing readiness."/></>;
  const left = remaining(batch);
  return <><PageHeader eyebrow="A NEW ROUTE. THE SAME PURPOSE." title="Dynamic Produce Routing" description="AgriRoute checks real inventory, matching attempts and risk signals before creating a routing case."/>
    <section className="panel match-selector"><label className="field"><span>Select produce batch</span><select value={batch.id} onChange={event => setId(event.target.value)}>{produce.map(item => <option value={item.id} key={item.id}>{item.crop} · {item.id}</option>)}</select></label><div><small>Remaining inventory</small><strong>{left} kg</strong></div><div><small>Current risk</small><strong>{batch.risk}</strong></div><div><small>Quality grade</small><strong>{batch.grade}</strong></div></section>
    {error && <div className="panel" role="alert">{error}</div>}
    <div className="routing-grid"><section className="panel route-column"><div className="route-label"><Clock size={18}/>01 / PRIMARY MATCHING</div><h2>Record a real matching attempt</h2><p className="muted">This records the server’s current match count. It does not simulate elapsed time or invent a rejection.</p><button className="button" disabled={!left} onClick={() => advance(batch.id)}>Record matching attempt<ArrowRight size={16}/></button></section>
      <section className="panel route-column decision"><div className="route-label"><GitBranch size={18}/>02 / ROUTING READINESS</div><h2>{readiness?.rerouting_candidate ? 'Review is available' : 'Primary matching continues'}</h2><p className="muted">Readiness is evaluated by the API from documented risk rules.</p>{readiness ? <><div className="decision-factors"><div><span>Failed unmatched attempts</span><strong>{readiness.failed_matching_attempts}</strong></div><div><span>Urgency</span><Badge tone={readiness.evaluated_urgency === 'LOW' ? 'green' : 'amber'}>{readiness.evaluated_urgency}</Badge></div><div><span>Recommended action</span><strong>{readiness.recommended_action.replaceAll('_',' ')}</strong></div></div>{readiness.reasons.map(reason => <p className="muted" key={reason}>{reason}</p>)}{readiness.warnings.map(warning => <p className="muted" key={warning}>{warning}</p>)}</> : <p className="muted">Checking readiness…</p>}</section>
      <section className="panel route-column alternative"><div className="route-label"><Factory size={18}/>03 / ALTERNATIVE ROUTE</div><h2>{activeCase ? 'Processor review in progress' : 'Create a routing case when eligible'}</h2><p className="muted">Processor requirements and explicit suitability checks determine eligible destinations.</p>{activeCase ? <div className="info-list"><div><span>Routing case</span><strong>#{activeCase.id}</strong></div><div><span>Status</span><strong>{activeCase.status}</strong></div><div><span>Case quantity</span><strong>{Number(activeCase.quantity_kg)} kg</strong></div></div> : <p>{readiness?.rerouting_candidate ? 'Reload after the matching attempt to open the eligible routing case.' : 'No routing case has been opened for this batch.'}</p>}<Link className="button secondary full" to={`/farmer/produce/${batch.id}`}>View batch history<ArrowRight size={16}/></Link></section></div>
    <div className="safety-note"><ShieldCheck size={20}/><div><strong>Compatibility and suitability are checked before alternative allocation.</strong><p>Risk review and buyer feedback do not certify food safety. Processors must record an explicit condition assessment.</p></div></div>
  </>;
}
