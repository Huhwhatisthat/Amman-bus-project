import './style.css'
import { BusService } from './busService'
import type { BusDisplay } from './types'

const busService = new BusService();

// Create the initial UI
const app = document.querySelector<HTMLDivElement>('#app')!;
app.innerHTML = `
  <div class="bus-display">
    <div class="screen">
      <div class="column">
        <div class="column-header">Near Side</div>
        <div id="downstairs-buses" class="loading">Loading...</div>
      </div>
      <div class="column">
        <div class="column-header">Opposite</div>
        <div id="opposite-buses" class="loading">Loading...</div>
      </div>
    </div>
  </div>
`;

function renderBuses(buses: BusDisplay[], containerId: string) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (buses.length === 0) {
    container.innerHTML = '<div class="loading">No buses nearby</div>';
    return;
  }

  container.innerHTML = buses.map(bus => {
    const firstTime = bus.isArriving ? 'Arr' : bus.minutesAway;
    const secondTime = bus.secondMinutes;
    
    return `
      <div class="bus-row">
        <div class="route-info">
          <div class="route-number">${bus.route}</div>
          <div class="destination">${bus.destination}</div>
        </div>
        <div class="time ${bus.isArriving ? 'arriving' : ''}">${firstTime}</div>
        ${secondTime ? `<div class="time">${secondTime}</div>` : '<div></div>'}
        <div class="bus-icon">${bus.busIcon ? '🚌' : ''}</div>
      </div>
    `;
  }).join('');
}

// Start listening to live data
busService.startListening((downstairs, opposite) => {
  // console.log('Bus data updated:', { downstairs, opposite });
  renderBuses(downstairs, 'downstairs-buses');
  renderBuses(opposite, 'opposite-buses');
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  busService.stopListening();
});
