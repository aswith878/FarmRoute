import { useMemo, useState } from 'react';
import { Users, Factory, Package, Scale, GitBranch, Sprout, Search, UserRoundCheck, UserRoundX } from 'lucide-react';
import { useStore } from '../../hooks/useStore';
import { remaining } from '../../data/mock';
import { PageHeader, StatCard, Badge, SectionHead, number, Field, EmptyState, Modal } from '../../components/UI';

const roleLabels = { FARMER: 'Farmer', BUYER: 'Primary buyer', PROCESSOR: 'Processor', ADMIN: 'Administrator' };

export default function Admin() {
  const { user, produce, users, transactions, loading, loadError, setAccountActive } = useStore();
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [pendingAccount, setPendingAccount] = useState(null);
  const [saving, setSaving] = useState(false);
  const activeAdmins = users.filter(person => person.role === 'ADMIN' && person.is_active).length;
  const visibleUsers = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    return users.filter(person => (roleFilter === 'ALL' || person.role === roleFilter)
      && (statusFilter === 'ALL' || (statusFilter === 'ACTIVE') === person.is_active)
      && (!needle || `${person.name} ${person.email} ${person.phone ?? ''}`.toLocaleLowerCase().includes(needle)));
  }, [users, search, roleFilter, statusFilter]);

  if (loading) return <section className="panel"><p className="muted">Loading network data…</p></section>;
  if (loadError) return <section className="panel"><h2>Network data unavailable</h2><p role="alert">{loadError}</p></section>;
  const sales = produce.reduce((sum, item) => sum + item.sold, 0);
  const routed = produce.reduce((sum, item) => sum + item.rerouted, 0);
  const total = produce.reduce((sum, item) => sum + item.quantity, 0);
  const roleCount = role => users.filter(person => person.role === role && person.is_active).length;
  const statuses = [['Available', produce.filter(item => remaining(item) > 0).length, 'green'], ['At routing review', produce.filter(item => item.eligible && remaining(item) > 0).length, 'purple'], ['Fully allocated', produce.filter(item => remaining(item) === 0).length, 'blue']];
  const risk = ['Low', 'Medium', 'High', 'Critical'].map(label => [label, produce.filter(item => item.risk === label && remaining(item) > 0).length]);
  const ratio = total ? (sales + routed) / total * 100 : 0;

  async function confirmAccountChange() {
    if (!pendingAccount) return;
    setSaving(true);
    const saved = await setAccountActive(pendingAccount, !pendingAccount.is_active);
    setSaving(false);
    if (saved) setPendingAccount(null);
  }

  return <><PageHeader eyebrow="THE BIGGER PICTURE" title="Harvests moving. Value growing." description="Live account, inventory and transaction data from AgriRoute."><Badge tone="blue">LIVE DATA</Badge></PageHeader>
    <div className="stats-grid six"><StatCard label="Farmers" value={roleCount('FARMER')} icon={Sprout} note="Active accounts"/><StatCard label="Primary buyers" value={roleCount('BUYER')} icon={Users} note="Active accounts"/><StatCard label="Processors" value={roleCount('PROCESSOR')} icon={Factory} note="Active accounts"/><StatCard label="Available produce" value={statuses[0][1]} icon={Package} note={`${produce.length} total batches`}/><StatCard label="Primary sales" value={number(sales)} unit="kg" icon={Scale} note={`${transactions.length} recorded transactions`}/><StatCard label="Rerouted quantity" value={number(routed)} unit="kg" icon={GitBranch} note="Alternative allocations"/></div>
    <div className="admin-charts"><section className="panel"><h2>Produce status</h2><div className="chart-bars">{statuses.map(([label,count,tone]) => <div key={label}><div><span>{label}</span><strong>{count} batches</strong></div><div className={`bar-track ${tone}`}><span style={{width:`${produce.length ? count/produce.length*100 : 0}%`}}/></div></div>)}</div></section>
      <section className="panel"><h2>Allocation totals</h2><div className="donut" style={{background:`conic-gradient(var(--primary) 0 ${total ? sales/total*100 : 0}%, var(--purple) ${total ? sales/total*100 : 0}% ${total ? (sales+routed)/total*100 : 0}%, var(--line) ${total ? (sales+routed)/total*100 : 0}% 100%)`}}><div><strong>{Math.round(ratio)}%</strong><span>allocated</span></div></div><div className="chart-legend"><span><i/>Primary · {number(sales)} kg</span><span><i/>Alternative · {number(routed)} kg</span><span><i/>Remaining · {number(total-sales-routed)} kg</span></div></section>
      <section className="panel"><h2>Risk distribution</h2><div className="chart-bars">{risk.map(([label,count]) => <div key={label}><div><Badge tone={label==='Critical'||label==='High'?'red':label==='Medium'?'amber':'green'}>{label}</Badge><strong>{count} batches</strong></div><div className={`bar-track ${label.toLowerCase()}`}><span style={{width:`${produce.length ? count/produce.length*100 : 0}%`}}/></div></div>)}</div><small className="muted">Backend risk labels · Not an ML prediction</small></section></div>

    <section className="panel admin-accounts">
      <SectionHead title="Account access" description="Review accounts and control access. Deactivation preserves the account and its records."/>
      <div className="account-filters">
        <Field label="Search accounts"><span className="account-search"><Search size={17}/><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Name, email, or phone"/></span></Field>
        <Field label="Role"><select value={roleFilter} onChange={event => setRoleFilter(event.target.value)}><option value="ALL">All roles</option>{Object.entries(roleLabels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
        <Field label="Status"><select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="ALL">All accounts</option><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></select></Field>
      </div>
      <div className="account-table" role="table" aria-label="Platform accounts">
        <div className="account-row account-head" role="row"><span role="columnheader">Account</span><span role="columnheader">Role</span><span role="columnheader">Status</span><span role="columnheader">Access</span></div>
        {visibleUsers.map(person => {
          const isSelf = person.id === user?.id;
          const lastAdmin = person.role === 'ADMIN' && person.is_active && activeAdmins <= 1;
          const actionDisabled = isSelf || lastAdmin;
          const reason = isSelf ? 'You cannot change access to your own account.' : lastAdmin ? 'At least one active administrator must remain.' : '';
          return <div className="account-row" role="row" key={person.id}>
            <div className="account-identity" role="cell"><strong>{person.name}{isSelf && <span className="muted"> · You</span>}</strong><small>{person.email}</small>{person.phone && <small>{person.phone}</small>}</div>
            <span role="cell">{roleLabels[person.role] ?? person.role}</span>
            <span role="cell"><Badge tone={person.is_active ? 'green' : 'neutral'}>{person.is_active ? 'Active' : 'Inactive'}</Badge></span>
            <div className="account-action" role="cell"><button type="button" className={`button ${person.is_active ? 'secondary' : ''}`} disabled={actionDisabled} title={reason} onClick={() => setPendingAccount(person)}>{person.is_active ? <><UserRoundX size={15}/>Deactivate</> : <><UserRoundCheck size={15}/>Activate</>}</button>{reason && <small className="muted">{reason}</small>}</div>
          </div>;
        })}
        {!visibleUsers.length && <EmptyState title="No accounts match" description="Try a different name, role, or status."/>}
      </div>
      <small className="muted">{visibleUsers.length} of {users.length} accounts · Deactivated users cannot sign in. Their history remains available to authorized administrators.</small>
    </section>

    <section className="panel"><SectionHead title="Platform activity" description="Recent events from batch traceability records."/><div className="data-table"><div className="table-row table-head"><span>Batch</span><span>Activity</span><span>Timestamp</span></div>{produce.flatMap(item => item.history.map((event,index) => ({item,event,index}))).slice(-14).reverse().map(({item,event,index}) => <div className="table-row" key={`${item.id}-${index}`}><span className="mono">{item.id}</span><div><strong>{event.title}</strong><p>{event.detail}</p></div><span className="muted">{event.time}</span></div>)}</div>{!produce.length&&<p className="muted">No inventory activity is recorded yet.</p>}</section>
    {pendingAccount && <Modal title={`${pendingAccount.is_active ? 'Deactivate' : 'Activate'} account`} onClose={() => !saving && setPendingAccount(null)}><p><strong>{pendingAccount.name}</strong> · {roleLabels[pendingAccount.role]}</p><p className="muted">{pendingAccount.is_active ? 'This account will lose sign-in access. Existing produce, requirements, and transaction history will be preserved.' : 'This account will be able to sign in and use its role workspace again.'}</p><button className="button full" disabled={saving} onClick={confirmAccountChange}>{saving ? 'Saving…' : `Confirm ${pendingAccount.is_active ? 'deactivation' : 'activation'}`}</button></Modal>}
  </>;
}
