import { useEffect } from 'react';
import { Routes, Route, useLocation, Link } from 'react-router-dom';
import { PROJECT } from './constants/config';
import { Toast, EmptyState } from './components/UI';
import DashboardLayout from './layouts/DashboardLayout';
import { Landing, Login } from './pages/public/Public';
import Overview from './pages/farmer/Overview';
import { ProduceList, ProduceDetail } from './pages/farmer/Produce';
import AddProduce from './pages/farmer/AddProduce';
import Matches from './pages/farmer/Matches';
import Rerouting from './pages/farmer/Rerouting';
import { BuyerDashboard, Requirements } from './pages/buyer/Buyer';
import AvailableProduce from './pages/buyer/AvailableProduce';
import Processor from './pages/processor/Processor';
import Admin from './pages/admin/Admin';
export default function App(){const {pathname,hash}=useLocation();useEffect(()=>{document.title=`${PROJECT.name} · Every harvest, a way forward`;if(hash){requestAnimationFrame(()=>document.querySelector(hash)?.scrollIntoView({behavior:'smooth'}));}else window.scrollTo(0,0);},[pathname,hash]);return <><Routes><Route path="/" element={<Landing/>}/><Route path="/login" element={<Login/>}/><Route element={<DashboardLayout/>}><Route path="/farmer/dashboard" element={<Overview/>}/><Route path="/farmer/add-produce" element={<AddProduce/>}/><Route path="/farmer/produce" element={<ProduceList/>}/><Route path="/farmer/produce/:id" element={<ProduceDetail/>}/><Route path="/farmer/matches" element={<Matches/>}/><Route path="/farmer/rerouting" element={<Rerouting/>}/><Route path="/buyer/dashboard" element={<BuyerDashboard/>}/><Route path="/buyer/requirements" element={<Requirements/>}/><Route path="/buyer/available-produce" element={<AvailableProduce/>}/><Route path="/processor/dashboard" element={<Processor dashboard/>}/><Route path="/processor/rerouted-produce" element={<Processor/>}/><Route path="/admin/dashboard" element={<Admin/>}/></Route><Route path="*" element={<div className="not-found"><EmptyState title="This route hasn’t sprouted yet" description="Choose a workspace to get back to the harvest."/><Link className="button" to="/login">Open demo</Link></div>}/></Routes><Toast/></>;}

