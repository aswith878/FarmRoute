import { useEffect, useState } from 'react';
import { MapPin, ArrowRight, ShieldCheck } from 'lucide-react';
import { remaining } from '../../data/mock';
import { agriRouteApi } from '../../api/agriRoute';
import { useStore } from '../../hooks/useStore';
import { PageHeader, Badge, Modal, EmptyState, Field } from '../../components/UI';

export default function Matches({ buyerMode = false }) {
  const { produce, accept, loading, loadError } = useStore();
  const [id, setId] = useState('');
  const p = produce.find(item => item.id === id) ?? produce[0];
  const [matches, setMatches] = useState([]);
  const [matchError, setMatchError] = useState('');
  const [quantity, setQuantity] = useState('');
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const available = p ? remaining(p) : 0;

  useEffect(() => {
    if (!p?.apiId || buyerMode) { setMatches([]); return; }
    let live = true;
    agriRouteApi.primaryMatches(p.apiId).then(result => { if (live) { setMatches(result.matches); setMatchError(''); } })
      .catch(error => { if (live) { setMatches([]); setMatchError(error.message); } });
    return () => { live = false; };
  }, [p?.apiId, buyerMode]);

  if (loading) return <section className="panel"><p className="muted">Loading produce and buyer requirements…</p></section>;
  if (loadError) return <section className="panel"><p role="alert">{loadError}</p></section>;
  if (!p) return <><PageHeader title="Your next best match" description="Create a produce listing to discover compatible buyer requirements."/><EmptyState title="No produce listings yet" description="Your matching recommendations appear after you list produce."/></>;
  const amount = Math.min(Number(quantity) || selected?.matchable_quantity_kg || 0, available);
  return <><PageHeader title={buyerMode ? 'Available produce' : 'Your next best match'} description="Recommendations are calculated from active buyer requirements and current produce data."/>
    <div className="panel match-selector"><Field label="Select produce batch"><select value={p.id} onChange={event => { setId(event.target.value); setQuantity(''); }}>
      {produce.map(item => <option key={item.id} value={item.id}>{item.crop} · {item.id}</option>)}</select></Field>
      <div><small>Initial quantity</small><strong>{p.quantity} kg</strong></div><div><small>Already allocated</small><strong>{p.sold + p.rerouted} kg</strong></div><div><small>Remaining inventory</small><strong className="green-text">{available} kg</strong></div>
      <Field label="Sale quantity (kg)"><input type="number" min="0.001" step="0.001" max={available} value={quantity} onChange={event => setQuantity(event.target.value)}/></Field></div>
    <div className="info-banner"><ShieldCheck size={19}/><p>AgriRoute ranks current compatible requirements. Confirmations update both requirement and produce balances.</p><Badge tone="blue">LIVE MATCHES</Badge></div>
    {matchError && <div className="panel" role="alert">{matchError}</div>}
    {!matchError && !matches.length && <EmptyState title="No current buyer matches" description="Matching appears when active buyer requirements are compatible with this batch."/>}
    <div className="match-grid">{matches.map((match, index) => <article className="panel match-card" key={match.buyer_requirement_id}>
      <div className="match-top"><span className="buyer-avatar">{match.buyer_name.slice(0,2).toUpperCase()}</span><div><small>{index === 0 ? 'TOP RECOMMENDATION' : 'COMPATIBLE REQUIREMENT'}</small><h3>{match.buyer_name}</h3></div><div className="score"><strong>{match.match_score}%</strong><small>match</small></div></div>
      <div className="match-facts"><div><small>Matchable quantity</small><strong>{Number(match.matchable_quantity_kg)} kg</strong></div><div><small>Requirement balance</small><strong>{Number(match.remaining_buyer_requirement_kg)} kg</strong></div><div><small>Quality compatibility</small><strong>Grade {p.grade}</strong></div><div><small><MapPin size={13}/>Distance</small><strong>{match.distance_km == null ? 'Unverified' : `${match.distance_km} km`}</strong></div></div>
      <div className="match-actions"><button className="button secondary" onClick={() => setDetail(match)}>View match factors</button><button className="button" disabled={!Number.isFinite(Number(quantity)) || Number(quantity) <= 0 || Number(quantity) > available || Number(quantity) > Number(match.matchable_quantity_kg)} onClick={() => setSelected(match)}>Accept {quantity || 0} kg<ArrowRight size={15}/></button></div>
    </article>)}</div>
    {selected && <Modal title="Confirm primary sale" onClose={() => setSelected(null)}><p className="muted">{p.crop} → {selected.buyer_name}</p><div className="info-list"><div><span>Available quantity</span><strong>{available} kg</strong></div><div><span>Requirement balance</span><strong>{Number(selected.remaining_buyer_requirement_kg)} kg</strong></div><div><span>Quantity being accepted</span><strong>{Number(quantity)} kg</strong></div><div className="highlight"><span>Remaining farmer inventory</span><strong>{available-Number(quantity)} kg</strong></div></div><p className="modal-explain">The sale is recorded against the selected buyer requirement.</p><button className="button full" onClick={async () => { const ok = await accept(p.id, Number(quantity), selected.buyer_name, false, selected.buyer_requirement_id); if (ok) setSelected(null); }}>Accept {quantity} kg</button></Modal>}
    {detail && <Modal title="AgriRoute match details" onClose={() => setDetail(null)}><h3>{detail.buyer_name}</h3><Badge tone="blue">MATCH SCORE · {detail.match_score}%</Badge><div className="factor-list">{Object.entries(detail.score_breakdown).map(([key, value]) => <div key={key}><span>{key.replaceAll('_',' ')}</span><strong>{value}%</strong><div className="progress"><span style={{width:`${value}%`}}/></div></div>)}</div>{detail.warnings.map(warning => <p className="muted" key={warning}>{warning}</p>)}</Modal>}
  </>;
}
