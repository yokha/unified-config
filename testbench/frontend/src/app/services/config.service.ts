import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class ConfigService {
  private apiUrl = 'http://localhost:8080/config/export'; // FastAPI backend URL

  constructor(private http: HttpClient) {}

  // Fetch all configs
  getConfigs(): Observable<any> {
    return this.http.get<any>(this.apiUrl);
  }
}
