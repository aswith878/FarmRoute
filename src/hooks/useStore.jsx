import { useContext, useState } from 'react';
import { initialProduce, remaining, buyers } from '../data/mock';
import { StoreContext as Store } from './StoreContext';
function read(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } }
export function StoreProvider({ children }) {
 const [produce, setProduce] = useState(() => read('agriroute-produce-v1', initialProduce));
 const [role, setRole] = useState(() => read('agriroute-role', 'farmer'));
 const [requirements, setRequirements] = useState(() => read('agriroute-requirements', []));
 const [toast, setToast] = useState('');
 function notify(message) { setToast(message); }
 function update(fn) { setProduce(prev => { const next = fn(prev); localStorage.setItem('agriroute-produce-v1', JSON.stringify(next)); return next; }); }
 function selectRole(next) { setRole(next); localStorage.setItem('agriroute-role', JSON.stringify(next)); }
 function accept(id, amount, buyer, alternative = false) {
  const p = produce.find(item => item.id === id);
  if (!p || amount <= 0 || amount > remaining(p) || (alternative && !p.eligible)) { notify('This allocation is no longer available. Please review the quantity.'); return false; }
  update(items => items.map(item => item.id !== id ? item : { ...item, salesValue: (item.salesValue ?? item.sold * (item.price - 1)) + (alternative ? 0 : amount * (buyers.find(b => b.name === buyer)?.price ?? item.price)), recoveryValue: (item.recoveryValue ?? item.rerouted * 18) + (alternative ? amount * 18 : 0), sold: item.sold + (alternative ? 0 : amount), rerouted: item.rerouted + (alternative ? amount : 0), history: [...item.history, { title: `${buyer} accepted ${amount} kg`, detail: alternative ? 'Compatible alternative allocation · Pickup confirmed' : `${remaining(item) - amount} kg remaining · Primary matching continues`, time: 'Demo · Just now' }] }));
  notify(alternative ? `${amount} kg successfully rerouted. Value recovered.` : `${amount} kg accepted. Remaining inventory is re-matched with primary buyers.`); return true;
 }
 function reset(showcase = false) { update(() => showcase ? initialProduce : initialProduce.map(p => p.id === 'AGR-TOM-001' ? { ...p, sold: 0, rerouted: 0, salesValue: 0, recoveryValue: 0, grade: 'A', risk: 'Low', eligible: false, age: 'Just listed', history: p.history.slice(0, 2) } : p)); notify(showcase ? 'Showcase restored. 150 kg of tomatoes is ready for compatible rerouting.' : 'Demo reset. Start with 1,000 kg of fresh tomatoes.'); }
 function advance() { const p = produce.find(p => p.id === 'AGR-TOM-001'); if (remaining(p) === 0) return; update(items => items.map(p => p.id !== 'AGR-TOM-001' ? p : { ...p, eligible: true, risk: 'High', grade: 'B', age: '3 days', history: [...p.history, { title: 'Risk increased · Rerouting eligible', detail: 'Demo time progression: repeated primary attempts unmatched, shelf life reduced; destination checks required', time: 'Demo · Day 3' }] })); notify('Day 3 simulated: high urgency and repeated unmatched attempts allow rerouting.'); }
 return <Store.Provider value={{ produce, role, selectRole, requirements, addRequirement: r => { const next = [...requirements, r]; setRequirements(next); localStorage.setItem('agriroute-requirements', JSON.stringify(next)); notify('Requirement saved. Browse compatible produce.'); }, notify, toast, setToast, accept, reset, advance, addProduce: p => { update(items => [p, ...items]); notify('Produce submitted. Primary matching is active.'); } }}>{children}</Store.Provider>;
}
export const useStore = () => useContext(Store);

