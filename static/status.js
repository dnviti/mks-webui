/* ------------------------------------------------------------
   Live-poll printer status and keep the last good data
   ------------------------------------------------------------ */

   let lastData = {};          // snapshot of the latest complete state

   async function refresh() {
     try {
       const resp = await fetch("/api/v1/printers/1/status");
       if (!resp.ok) throw new Error(resp.statusText);
       const incoming = await resp.json();
   
       /* -------- deep-merge: overwrite only keys that arrived -------- */
       lastData = {
         ...lastData,
         ...incoming,                       // top-level keys
         temps: {
           ...(lastData.temps || {}),
           ...(incoming.temps || {})        // per-temperature keys
         }
       };
     } catch (err) {
       // network error or server hiccup → keep displaying lastData
       console.error("[poll error]", err);
     }
   
     /* ---------- render UI from lastData (never undefined) ---------- */
     const {
       temps   = {},
       progress = 0,
       job     = "—",
       elapsed = "00:00:00",
       stamp   = "—",
       state   = "UNKNOWN"
     } = lastData;
   
     setTxt("t-nozzle",      temps.T);
     setTxt("t-nozzle-set",  temps.Tset);
     setTxt("t-bed",         temps.B);
     setTxt("t-bed-set",     temps.Bset);
   
     setTxt("job",     job);
     setTxt("elapsed", elapsed);
     setTxt("stamp",   stamp);
   
     updateProgress(progress);
     updateStateBadge(state);
   }
   
   /* -------------------- helpers -------------------- */
   
   function setTxt(id, value) {
     const el = document.getElementById(id);
     if (el && value !== undefined && value !== null) el.textContent = value;
   }
   
   function updateProgress(val) {
     const bar = document.getElementById("progress-bar");
     const txt = document.getElementById("progress-text");
     if (!bar || !txt) return;
     bar.style.width   = `${val}%`;
     bar.ariaValueNow  = val;
     txt.textContent   = val;
   }
   
   function updateStateBadge(state) {
     const badge = document.getElementById("state-badge");
     if (!badge) return;
     badge.textContent = state;
     badge.className   = "badge";          // reset classes
     if      (state === "PRINTING") badge.classList.add("text-bg-success");
     else if (state === "PAUSED")   badge.classList.add("text-bg-warning");
     else                           badge.classList.add("text-bg-secondary");
   }
   
   /* --------------- kick things off --------------- */
   refresh();                // run once immediately
   setInterval(refresh, 1000);  // then every second
   