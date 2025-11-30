import { db } from './firebase';
import { collection, onSnapshot, query } from 'firebase/firestore';
import type { RouteDocument, BusDisplay } from './types';

export class BusService {
  private unsubscribe: (() => void) | null = null;

  /**
   * Listen to live bus data updates
   */
  startListening(callback: (downstairs: BusDisplay[], opposite: BusDisplay[]) => void) {
    const liveDataRef = collection(db, 'live_data');
    const q = query(liveDataRef);

    this.unsubscribe = onSnapshot(q, (snapshot) => {
      
      const allRoutes: Map<string, RouteDocument> = new Map();
      
      snapshot.forEach((doc) => {
        allRoutes.set(doc.id, doc.data() as RouteDocument);
      });


      // Process the data and split into downstairs/opposite
      const { downstairs, opposite } = this.processRouteData(allRoutes);
      
      callback(downstairs, opposite);
    }, (error) => {
      console.error('Error listening to live data:', error);
    });
  }

  /**
   * Process route data and calculate arrival times
   */
  private processRouteData(routes: Map<string, RouteDocument>): {
    downstairs: BusDisplay[];
    opposite: BusDisplay[];
  } {
    const downstairs: BusDisplay[] = [];
    const opposite: BusDisplay[] = [];

    routes.forEach((routeData, routeId) => {
      // Parse route ID: route_100_dir_0
      const match = routeId.match(/route_(\w+)_dir_([01])/);
      if (!match) return;

      const [, routeNumber, direction] = match;
      const buses = routeData.buses || [];
      
      if (buses.length === 0) return;

      // Calculate minutes since last_seen for the entire route
      const lastSeenMs = routeData.last_seen.seconds * 1000;
      const now = Date.now();
      const minutesSinceUpdate = Math.floor((now - lastSeenMs) / 60000);
      
      // Only show routes updated in last 30 minutes
      if (minutesSinceUpdate > 30) return;

      // For now, show route with bus count and estimated arrival
      // We'll need user's location to calculate actual arrival times
      const busDisplay: BusDisplay = {
        route: routeNumber,
        direction: direction,
        destination: this.getDestination(routeNumber, direction),
        minutesAway: Math.max(1, 5 - minutesSinceUpdate), // Rough estimate
        secondMinutes: buses.length > 1 ? Math.max(2, 10 - minutesSinceUpdate) : undefined,
        isArriving: minutesSinceUpdate < 1,
        busIcon: true
      };

      // Split by direction (dir_0 = downstairs, dir_1 = opposite)
      if (direction === '0') {
        downstairs.push(busDisplay);
      } else {
        opposite.push(busDisplay);
      }
    });

    // Sort by minutes away
    downstairs.sort((a, b) => a.minutesAway - b.minutesAway);
    opposite.sort((a, b) => a.minutesAway - b.minutesAway);

    return { downstairs, opposite };
  }

  /**
   * Get destination name based on route and direction
   * This is a placeholder - you should populate with actual route data
   */
  private getDestination(routeNumber: string, direction: string): string {
    // Map of route destinations - you can expand this
    const destinations: Record<string, { 0: string; 1: string }> = {
      '100': { 0: 'to Sweileh', 1: 'to Marbat Bridge' },
      '99': { 0: 'to Sweileh', 1: 'to Jordan Musuem' },
      '98': { 0: 'to Sweileh', 1: 'to Tareq terminal' },
      // '52': { 0: 'to Downtown', 1: 'to Abdali' },
      // Add more routes as needed
    };

    const route = destinations[routeNumber];
    if (route) {
      return direction === '0' ? route[0] : route[1];
    }
    
    // Default fallback
    return direction === '0' ? 'Direction A' : 'Direction B';
  }

  /**
   * Stop listening to updates
   */
  stopListening() {
    if (this.unsubscribe) {
      this.unsubscribe();
      this.unsubscribe = null;
    }
  }
}
