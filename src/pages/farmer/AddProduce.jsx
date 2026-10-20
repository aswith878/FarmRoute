import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UploadCloud, Check, ScanLine, Save, ArrowRight, X } from 'lucide-react';
import { useStore } from '../../hooks/useStore';
import { PageHeader, Field, Badge } from '../../components/UI';

const today = new Date().toISOString().slice(0, 10);
const inThreeDays = new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10);
const defaults = {
  crop: '', category: 'Vegetables', quantity: '', price: '', harvest: today,
  until: inThreeDays, location: 'Puducherry', storage: 'Shaded ambient storage',
  grade: 'A', condition: 'No visible damage', freshness: 'Good', defects: 'None', notes: '',
};
const imageTypes = ['image/png', 'image/jpeg', 'image/webp'];

export default function AddProduce() {
  const { addProduce, notify } = useStore();
  const navigate = useNavigate();
  const [form, setForm] = useState(() => {
    try { return { ...defaults, ...JSON.parse(localStorage.getItem('agriroute-draft')) }; }
    catch { return defaults; }
  });
  const [image, setImage] = useState('');
  const [imageFile, setImageFile] = useState(null);
  const [assessed, setAssessed] = useState(false);
  const [saving, setSaving] = useState(false);
  const input = useRef(null);

  const update = (key, value) => setForm(current => ({ ...current, [key]: value }));
  const field = (key, label, type = 'text', options) => (
    <Field label={label} key={key}>
      {options
        ? <select value={form[key]} onChange={event => update(key, event.target.value)}>
            {options.map(option => <option key={option}>{option}</option>)}
          </select>
        : <input required={key !== 'notes'} type={type}
            min={type === 'number' ? '1' : undefined}
            step={key === 'price' ? '0.01' : undefined}
            minLength={type === 'text' ? 2 : undefined}
            value={form[key]} onChange={event => update(key, event.target.value)} />}
    </Field>
  );

  function chooseImage(file) {
    if (!file) return;
    if (!imageTypes.includes(file.type) || file.size > 5 * 1024 * 1024) {
      notify('Choose a PNG, JPG or WebP image no larger than 5 MB.');
      if (input.current) input.current.value = '';
      return;
    }
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = () => { setImage(reader.result); setAssessed(false); };
    reader.onerror = () => {
      setImage(''); setImageFile(null);
      notify('The image could not be previewed. Please choose it again.');
    };
    reader.readAsDataURL(file);
    if (input.current) input.current.value = '';
  }

  async function submit(event) {
    event.preventDefault();
    if (saving) return;
    if (form.until && form.until < form.harvest) {
      notify('Availability must be on or after the harvest date.');
      return;
    }
    setSaving(true);
    try {
      const batch = await addProduce(form, imageFile);
      if (!batch) return;
      localStorage.removeItem('agriroute-draft');
      navigate(`/farmer/produce/${batch.batch_code}`);
    } finally { setSaving(false); }
  }

  return <>
    <PageHeader title="Give your harvest a head start" description="A few details help your produce find the right market." />
    <form onSubmit={submit}>
      <div className="form-layout">
        <div>
          <section className="panel form-section">
            <div className="form-section-title"><span>01</span><div><h2>Produce information</h2><p>The essentials about your harvest.</p></div></div>
            <div className="form-grid">
              {field('crop', 'Crop name')}
              {field('category', 'Category', 'text', ['Vegetables', 'Fruits', 'Grains', 'Pulses'])}
              {field('quantity', 'Quantity (kg)', 'number')}
              {field('price', 'Expected price (₹/kg)', 'number')}
              {field('harvest', 'Harvest date', 'date')}
              {field('until', 'Available until', 'date')}
              {field('location', 'Location')}
              {field('storage', 'Storage type', 'text', ['Shaded ambient storage', 'Cool storage', 'Ventilated storage'])}
            </div>
          </section>
          <section className="panel form-section">
            <div className="form-section-title"><span>02</span><div><h2>Quality information</h2><p>Better information. Better compatibility.</p></div></div>
            <div className="form-grid">
              {field('grade', 'Quality grade', 'text', ['A', 'B'])}
              {field('condition', 'Visible condition', 'text', ['No visible damage', 'Minor surface damage', 'Requires physical review'])}
              {field('freshness', 'Freshness', 'text', ['Good', 'Moderate', 'Needs review'])}
              {field('defects', 'Cosmetic defects', 'text', ['None', 'Size variation', 'Surface blemishes'])}
              <Field label="Additional notes"><textarea rows="3" value={form.notes} onChange={event => update('notes', event.target.value)} placeholder="Handling details or pickup instructions…" /></Field>
            </div>
          </section>
        </div>
        <aside>
          <section className="panel form-section">
            <div className="form-section-title"><span>03</span><div><h2>A picture of your harvest</h2><p>Optional · saved with this listing.</p></div></div>
            <div className="upload-zone" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); chooseImage(event.dataTransfer.files[0]); }}>
              {image
                ? <><img src={image} alt="Produce listing preview" /><button type="button" className="icon-button" aria-label="Remove uploaded image" onClick={() => { setImage(''); setImageFile(null); setAssessed(false); }}><X size={17} /></button></>
                : <><UploadCloud size={35} /><h4>Drop your produce image here</h4><p>PNG, JPG or WebP · up to 5 MB</p></>}
              <button type="button" className="button secondary" onClick={() => input.current?.click()}>{image ? 'Choose another image' : 'Browse files'}</button>
              <input ref={input} hidden type="file" accept="image/png,image/jpeg,image/webp" onChange={event => chooseImage(event.target.files[0])} />
            </div>
            <button type="button" className="button secondary full" disabled={!image} onClick={() => setAssessed(true)}><ScanLine size={17} />Simulate visual assessment</button>
            {assessed && <div className="assessment"><ScanLine className="scan-icon" size={25} /><h3>Visual Quality Assessment</h3><Badge tone="blue">91% CONFIDENCE · DEMO</Badge><div className="info-list"><div><span>Grade</span><strong>A</strong></div><div><span>Freshness</span><strong>Good</strong></div><div><span>Visible damage</span><strong>Low</strong></div><div><span>Cosmetic variation</span><strong>Minor</strong></div></div><small>Fixed sample result; no image analysis is performed. Your manually selected grade controls this listing.</small></div>}
            <p className="safety-note">Prototype visual assessment. Final suitability should consider additional physical and handling information.</p>
          </section>
        </aside>
      </div>
      <div className="form-footer"><span><Check size={16} />Your produce listing is saved to AgriRoute.</span><div>
        <button type="button" className="button secondary" disabled={saving} onClick={() => { localStorage.setItem('agriroute-draft', JSON.stringify(form)); notify('Draft saved on this device.'); }}><Save size={16} />Save draft</button>
        <button className="button" type="submit" disabled={saving}>{saving ? 'Saving listing…' : 'Submit produce'}<ArrowRight size={16} /></button>
      </div></div>
    </form>
  </>;
}
