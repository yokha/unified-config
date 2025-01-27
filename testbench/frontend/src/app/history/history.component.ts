import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatInputModule } from '@angular/material/input';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatSortModule } from '@angular/material/sort';
import { JsonPipe } from '@angular/common';

@Component({
  selector: 'app-history',
  templateUrl: './history.component.html',
  styleUrls: ['./history.component.scss'],
  standalone: true,
  imports: [
    FormsModule,
    MatTableModule,
    MatButtonModule,
    MatCardModule,
    MatInputModule,
    MatToolbarModule,
    MatSortModule,
    JsonPipe,
  ],
})
export class HistoryComponent {
  history: any[] = [];
  section: string = '';
  key: string = '';
  limit: number = 10;
  offset: number = 0;
  totalCount: number = 0;
  totalPages: number = 1;
  currentPage: number = 1;
  sortOrder: { [key: string]: boolean } = {};

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.fetchHistory();
  }

  applyFilter() {
    this.offset = 0;
    this.currentPage = 1;
    this.fetchHistory();
  }

  fetchHistory() {
    let apiUrl = `http://localhost:8080/config/history?limit=${this.limit}&offset=${this.offset}`;

    if (this.section.trim() !== '') {
      apiUrl += `&section=${this.section}`;
    }

    if (this.key.trim() !== '') {
      apiUrl += `&key=${this.key}`;
    }

    this.http.get<any>(apiUrl).subscribe((response) => {
      console.log('API Response:', response);
      this.history = [...(response.data || [])]; // ✅ Force array change detection
      this.totalCount = response.total_count || 0;
      this.totalPages = Math.ceil(this.totalCount / this.limit);
    });
  }

  nextPage() {
    if (this.currentPage < this.totalPages) {
      this.offset += this.limit;
      this.currentPage++;
      this.fetchHistory();
    }
  }

  prevPage() {
    if (this.currentPage > 1) {
      this.offset -= this.limit;
      this.currentPage--;
      this.fetchHistory();
    }
  }

  sortBy(field: string) {
    this.sortOrder[field] = !this.sortOrder[field];

    this.history = [...this.history.sort((a, b) => {
      if (a[field] > b[field]) return this.sortOrder[field] ? 1 : -1;
      if (a[field] < b[field]) return this.sortOrder[field] ? -1 : 1;
      return 0;
    })]; // ✅ Assign a **new array reference** to trigger UI update
  }
}
