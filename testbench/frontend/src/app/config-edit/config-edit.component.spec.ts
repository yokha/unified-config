import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ConfigEditComponent } from './config-edit.component';

describe('ConfigEditComponent', () => {
  let component: ConfigEditComponent;
  let fixture: ComponentFixture<ConfigEditComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ConfigEditComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ConfigEditComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
