// Fetch /printer/status every 3 s and update the table
async function refresh() {
    try {
      const r = await fetch('/printer/status');
      if (!r.ok) throw new Error(r.statusText);
      const d = await r.json();
  
      // Simple DOM patches
      if (d.temps) {
        document.getElementById('t-nozzle').textContent     = d.temps.T ?? document.getElementById('t-nozzle').textContent;
        document.getElementById('t-nozzle-set').textContent = d.temps.Tset ?? document.getElementById('t-nozzle-set').textContent;
        document.getElementById('t-bed').textContent        = d.temps.B ?? document.getElementById('t-bed').textContent;
        document.getElementById('t-bed-set').textContent    = d.temps.Bset ?? document.getElementById('t-bed-set').textContent;
      }
      document.getElementById('job').textContent = `${d.job ?? document.getElementById('job').textContent}`;
      document.getElementById('progress').textContent = d.progress ?? document.getElementById('progress').textContent;
      document.getElementById('elapsed').textContent  = d.elapsed ?? document.getElementById('elapsed').textContent;
      document.getElementById('state').textContent    = d.state  ?? document.getElementById('state').textContent;
      document.getElementById('stamp').textContent    = d.stamp  ?? document.getElementById('stamp').textContent;
    } catch (err) {
      console.error(err);
    }
  }
  setInterval(refresh, 1000);
  