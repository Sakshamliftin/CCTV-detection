import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Upload, HardDrive, RefreshCw } from 'lucide-react';

export function StoreUpload({ onStoreUploaded }) {
  const [file, setFile] = useState(null);
  const [posFile, setPosFile] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await api.uploadStore(formData);
      
      if (posFile) {
        const posData = new FormData();
        posData.append('file', posFile);
        await api.uploadPOS(res.store_id, posData);
      }
      
      onStoreUploaded(res.store_id);
    } catch (e) {
      alert("Error uploading store");
    }
    setLoading(false);
  };
  
  return (
    <div className="metric-card glass-panel" style={{ '--card-color': '#10b981', gridColumn: 'span 2' }}>
      <div className="metric-card-header">
        <h3 className="metric-title">Upload New Store</h3>
        <Upload size={20} color="#10b981" />
      </div>
      <div style={{ marginTop: 15, display: 'flex', gap: 15, alignItems: 'center' }}>
        <div>
          <label style={{display: 'block', marginBottom: 5, fontSize: 12}}>Store ZIP Folder:</label>
          <input type="file" accept=".zip" onChange={e => setFile(e.target.files[0])} />
        </div>
        <div>
          <label style={{display: 'block', marginBottom: 5, fontSize: 12}}>POS Data (CSV):</label>
          <input type="file" accept=".csv" onChange={e => setPosFile(e.target.files[0])} />
        </div>
        <button 
          onClick={handleUpload} 
          disabled={!file || loading}
          style={{ padding: '8px 16px', background: '#10b981', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
        >
          {loading ? 'Uploading...' : 'Upload & Process'}
        </button>
      </div>
    </div>
  );
}

export function StoreSelector({ currentStore, onSelectStore }) {
  const [stores, setStores] = useState([]);
  
  useEffect(() => {
    api.getStores()
      .then(res => {
        setStores(res.stores || []);
        if (res.stores && res.stores.length > 0) {
          onSelectStore(res.stores[0].id);
        }
      })
      .catch(() => setStores([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  return (
    <div className="metric-card glass-panel" style={{ '--card-color': '#8b5cf6', gridColumn: 'span 2' }}>
      <div className="metric-card-header">
        <h3 className="metric-title">Select Store</h3>
        <HardDrive size={20} color="#8b5cf6" />
      </div>
      <div style={{ marginTop: 15, display: 'flex', gap: 15, alignItems: 'center' }}>
        <select 
          value={currentStore || ""} 
          onChange={e => onSelectStore(e.target.value)}
          style={{ padding: '8px', background: 'rgba(255,255,255,0.1)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, width: '200px' }}
        >
          <option value="" disabled>Select a store</option>
          {stores.map(s => (
            <option key={s.id} value={s.id} style={{color: '#000'}}>{s.name} ({s.status})</option>
          ))}
        </select>
        
        {currentStore && (
          <button 
            onClick={() => api.processStore(currentStore).then(() => alert("Processing started!"))}
            style={{ padding: '8px 16px', background: '#8b5cf6', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}
          >
            <RefreshCw size={14} /> Process Clips
          </button>
        )}
      </div>
    </div>
  );
}
