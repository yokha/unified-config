import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { JsonPipe, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatSelectModule } from '@angular/material/select';
import { MatCardModule } from '@angular/material/card';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';

// ✅ Correct highlight.js import
import hljs from 'highlight.js/lib/core';
import json from 'highlight.js/lib/languages/json';
import yaml from 'highlight.js/lib/languages/yaml';
import toml from 'highlight.js/lib/languages/ini';

hljs.registerLanguage('json', json);
hljs.registerLanguage('yaml', yaml);
hljs.registerLanguage('toml', toml);

@Component({
  selector: 'app-export',
  templateUrl: './export.component.html',
  styleUrls: ['./export.component.scss'],
  standalone: true,
  imports: [JsonPipe, NgIf, FormsModule, MatSelectModule, MatCardModule, MatToolbarModule, MatButtonModule],
})
export class ExportComponent {
  configs: string = "";
  selectedFormat: string = 'json';
  highlightedConfig: string = "";

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.fetchConfig();
  }

  fetchConfig() {
    const apiUrl = `http://localhost:8080/config/export?format=${this.selectedFormat}`;

    this.http.get(apiUrl, { responseType: 'text' }).subscribe((data) => {
      this.configs = data;
      this.highlightConfig();
    });
  }

  highlightConfig() {
    let formattedConfig = this.configs;

    if (this.selectedFormat === 'json') {
      try {
        formattedConfig = JSON.stringify(JSON.parse(this.configs), null, 2);
      } catch (e) {
        console.error("JSON formatting error:", e);
      }
    }

    this.highlightedConfig = hljs.highlightAuto(formattedConfig, [this.selectedFormat]).value;
  }

  downloadConfig() {
    let contentToSave = this.configs;

    if (this.selectedFormat === 'json') {
      try {
        contentToSave = JSON.stringify(JSON.parse(this.configs), null, 2);
      } catch (e) {
        console.error("JSON formatting error:", e);
      }
    }

    const blob = new Blob([contentToSave], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `config.${this.selectedFormat}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  }
}
