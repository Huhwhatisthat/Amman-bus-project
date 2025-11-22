// Bus data types
export interface BusData {
  busId: string;
  lat: string;
  lng: string;
  bearing: string;
  load: string;
}

export interface RouteDocument {
  buses: BusData[];
  last_seen: {
    seconds: number;
    nanoseconds: number;
  };
}

export interface BusDisplay {
  route: string;
  direction: string; // e.g., "0" or "1"
  destination: string; // e.g., "to Sweileh"
  minutesAway: number;
  secondMinutes?: number;
  isArriving: boolean;
  busIcon: boolean;
}
