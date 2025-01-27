import { Component, OnInit, OnDestroy } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';  // ✅ Import CommonModule
import { NgZone } from '@angular/core'; // ✅ Import NgZone for UI updates

import yaml from 'js-yaml';
import toml from 'toml';
import hljs from 'highlight.js/lib/core';
import jsonLang from 'highlight.js/lib/languages/json';
import yamlLang from 'highlight.js/lib/languages/yaml';

hljs.registerLanguage('json', jsonLang);
hljs.registerLanguage('yaml', yamlLang);

@Component({
  selector: 'app-config-edit',
  templateUrl: './config-edit.component.html',
  styleUrls: ['./config-edit.component.scss'],
  standalone: true,
  imports: [FormsModule, CommonModule],  // ✅ Add CommonModule here
})
export class ConfigEditComponent implements OnInit, OnDestroy {
  configText: string = '';  
  selectedFormat: string = 'yaml';  
  isValid: boolean = true;  
  liveUpdates: { section: string; key: string; new_value: any }[] = [];  
  private ws: WebSocket | null = null;  

  constructor(private http: HttpClient, private ngZone: NgZone) {}

  ngOnInit() {
    this.fetchConfig();
    this.connectWebSocket();
  }

  fetchConfig() {
    const apiUrl = `http://localhost:8080/config/export?format=${this.selectedFormat}`;
    
    this.http.get(apiUrl, { responseType: 'text' }).subscribe(
      (data) => {
        if (this.selectedFormat === 'json') {
          try {
            this.configText = JSON.stringify(JSON.parse(data), null, 2); 
          } catch (e) {
            console.error("JSON formatting error:", e);
            this.configText = data;
          }
        } else {
          this.configText = data;
        }
        this.highlightConfig();
      },
      (error) => console.error('Error fetching config:', error)
    );
  }

  connectWebSocket() {
    if (this.ws) {
      this.ws.close();  // Ensure old connection is closed before reconnecting
    }
  
    this.ws = new WebSocket('ws://localhost:8080/config/updates');
  
    this.ws.onopen = () => {
      console.log("✅ WebSocket connected.");
    };
  
    this.ws.onmessage = (event) => {
      try {
        const update = JSON.parse(event.data);
        console.log('🔄 Live Config Update Received:', update);
  
        this.ngZone.run(() => {
          if (update.configs) {
            Object.entries(update.configs).forEach(([fullKey, newValue]) => {
              let [section, key] = fullKey.includes(":") ? fullKey.split(":") : ["global", fullKey];
  
              const formattedValue = typeof newValue === "object"
                ? JSON.stringify(newValue, null, 2)
                : newValue;
  
              // ✅ Only add changed values
              const existingIndex = this.liveUpdates.findIndex(
                (item) => item.section === section && item.key === key
              );
  
              if (existingIndex === -1 || this.liveUpdates[existingIndex].new_value !== formattedValue) {
                this.liveUpdates.unshift({ section, key, new_value: formattedValue });
  
                // ✅ Keep only last 20 updates
                if (this.liveUpdates.length > 20) {
                  this.liveUpdates.pop();
                }
              }
            });
          }
        });
  
        console.log('✅ Updated Live Updates:', this.liveUpdates);
      } catch (e) {
        console.error("❌ Error processing WebSocket message:", e);
      }
    };
  
    this.ws.onerror = (error) => {
      console.error("❌ WebSocket Error:", error);
    };
  
    this.ws.onclose = () => {
      console.warn("⚠️ WebSocket connection closed. Reconnecting...");
      setTimeout(() => this.connectWebSocket(), 5000);  // ✅ Auto-reconnect after 5s
    };
  }
  
  highlightConfig() {
    setTimeout(() => {
      const codeBlock = document.querySelector('pre code');
      if (codeBlock) {
        codeBlock.innerHTML = hljs.highlight(this.configText, { language: this.selectedFormat }).value;
      }
    }, 100);
  }

  validateConfig() {
      try {
          if (this.selectedFormat === 'json') {
              JSON.parse(this.configText);
          } else if (this.selectedFormat === 'yaml') {
              yaml.load(this.configText);
          } else if (this.selectedFormat === 'toml') {
              toml.parse(this.configText);
          }
          this.isValid = true;
      } catch (e) {
          console.error("Validation error:", e);
          this.isValid = false;
      }
  }

  submitConfig() {
    if (!this.isValid) {
        alert("Invalid configuration format!");
        return;
    }

    let parsedConfig;
    try {
        if (this.selectedFormat === 'json') {
            parsedConfig = JSON.parse(this.configText);
        } else if (this.selectedFormat === 'yaml') {
            parsedConfig = yaml.load(this.configText);
        } else if (this.selectedFormat === 'toml') {
            parsedConfig = toml.parse(this.configText);
        }
    } catch (e) {
        alert("Error parsing configuration.");
        return;
    }

    this.http.put('http://localhost:8080/config/update_bulk', parsedConfig).subscribe(
        () => alert("Configuration updated successfully!"),
        (error) => console.error("Failed to update config:", error)
    );
  }

  ngOnDestroy() {
    if (this.ws) {
      this.ws.close();
    }
  }
}
