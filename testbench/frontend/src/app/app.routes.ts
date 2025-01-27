import { Routes } from '@angular/router';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';

import { ExportComponent } from './export/export.component';
import { HistoryComponent } from './history/history.component';
import { ConfigEditComponent } from './config-edit/config-edit.component';

export const routes: Routes = [
  { path: '', component: ExportComponent },
  { path: 'history', component: HistoryComponent },
  { path: 'edit', component: ConfigEditComponent }, // ✅ New Config Edit Page
];

export const appConfig = {
  providers: [provideRouter(routes), provideHttpClient()],
};
