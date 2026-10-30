import {test,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';
const password=process.env.MI_E2E_PASSWORD!;
const origin='http://127.0.0.1:5173';

test('HR publishes a custom form; employee and manager complete it; HR sees approved results',async({page})=>{
 test.setTimeout(120000);
 const suffix=Date.now().toString(),email=`custom.${suffix}@example.org`,title=`Custom appraisal ${suffix}`;
 async function login(email:string,secret=password){const response=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email,password:secret}});expect(response.ok()).toBe(true);return {'X-CSRF-Token':(await response.json()).csrf_token,Origin:origin};}
 const h=await login('admin.e2e@example.org');
 await page.goto('/');await page.getByRole('button',{name:'Appraisal forms',exact:true}).click();await page.getByRole('button',{name:'Create form',exact:true}).click();
 await page.getByLabel('Form name',{exact:true}).fill(title);
 await page.getByRole('button',{name:'Add text section',exact:true}).click();
 await page.getByLabel('Section title',{exact:true}).fill('Personal impact');
 await page.getByLabel('Question 1',{exact:true}).fill('What changed for your customers?');
 await page.getByLabel('Required before submission / finalization').check();
 await page.getByRole('button',{name:'Preview form',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Personal impact',exact:true})).toBeVisible();
 page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Publish form version',exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:'Published version available'})).toBeVisible();
 const forms=await (await page.request.get('/api/v1/hr/forms/published')).json();const form=forms.find((f:{name:string})=>f.name.startsWith(title));expect(form).toBeTruthy();
 const managers=await (await page.request.get('/api/v1/admin/users?role=MANAGER&q=E2E-manager')).json();
 const created=await page.request.post('/api/v1/admin/users',{headers:h,data:{employee_id:`CUSTOM-${suffix}`,full_name:'Custom Form Employee',email,department:'Engineering',designation:'Engineer',country:'India',role:'EMPLOYEE',manager_id:managers.items[0].id,temporary_password:password}});expect(created.status()).toBe(201);const employee=await created.json();
 const cycle=await (await page.request.post('/api/v1/cycles',{headers:h,data:{title,form_version_id:form.id,period_start:'2026-01-01',period_end:'2026-12-31',submission_deadline:new Date(Date.now()+86400000).toISOString(),min_goals:1,allow_late_submission:false,participant_ids:[employee.id]}})).json();
 expect((await page.request.post(`/api/v1/cycles/${cycle.id}/activate`,{headers:h,data:{expected_version:1}})).ok()).toBe(true);
 const eh=await login(email);expect((await page.request.post('/api/v1/auth/change-password',{headers:eh,data:{current_password:password,new_password:password+'-custom'}})).ok()).toBe(true);
 await page.reload();await page.getByRole('button',{name:'Open self-assessment',exact:true}).click();
 await page.getByLabel('Responsibility / goal description',{exact:true}).fill('Customer service');await page.getByLabel('Achievements and self-assessment',{exact:true}).fill('Improved response times');
 await page.getByLabel('What changed for your customers? (required)',{exact:true}).fill('Customers received faster support.');
 await page.getByRole('button',{name:'Save and review submission',exact:true}).click();await expect(page.getByText('Customers received faster support.',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Submit to reporting manager',exact:true}).click();
 await expect(page.getByText('Your appraisal has been submitted to your reporting manager.',{exact:true})).toBeVisible();
 await login('manager.e2e@example.org');await page.reload();await page.getByRole('button',{name:'Team appraisals',exact:true}).click();await page.getByLabel('Find an employee').fill(`CUSTOM-${suffix}`);await page.getByRole('button',{name:/Open review/}).click();
 await expect(page.getByText('Customers received faster support.',{exact:true})).toBeVisible();
 const ratings=page.getByLabel('Manager rating',{exact:true});for(let i=0;i<await ratings.count();i++)await ratings.nth(i).selectOption('4');
 const comments=page.getByLabel('Supporting evaluation comment',{exact:true});for(let i=0;i<await comments.count();i++)await comments.nth(i).fill('Consistent delivery with evidence.');
 await page.getByLabel('What the employee did particularly well',{exact:true}).fill('Delivered customer improvements.');await page.getByLabel('How the employee could be more effective',{exact:true}).fill('Continue developing communication.');await page.getByRole('button',{name:'Save manager draft',exact:true}).click();await expect(page.getByText('Manager review draft saved.',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Review and finalize',exact:true}).click();await page.getByLabel('I confirm the appraisal review meeting has taken place').check();await page.getByRole('button',{name:'Confirm finalization',exact:true}).click();await expect(page.getByText('Evaluation finalized. Release it when you are ready to share the result.',{exact:true})).toBeVisible();
 await login('hr.e2e@example.org');await page.reload();await page.getByRole('button',{name:'HR monitoring',exact:true}).click();await expect(page.getByRole('heading',{name:'HR appraisal monitoring',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Final evaluations',exact:true}).click();await page.getByLabel('Search employee or manager').fill(`CUSTOM-${suffix}`);await page.getByRole('button',{name:'View final evaluation',exact:true}).click();await expect(page.getByText('Customers received faster support.',{exact:true})).toBeVisible();await expect(page.getByText('Overall score 3.6',{exact:false})).toBeVisible();
 for(const format of ['Excel','PDF']){const event=page.waitForEvent('download');await page.getByRole('button',{name:`Download evaluation · ${format}`,exact:true}).click();const downloaded=await event;expect(downloaded.suggestedFilename()).toContain(format==='Excel'?'.xlsx':'.pdf');expect(await downloaded.failure()).toBeNull();}
 await page.screenshot({path:'../.local/hr-final-evaluation.png',fullPage:true});
});

test('Excel import previews users and returns a working private setup link',async({page})=>{
 test.setTimeout(90000);const suffix=Date.now().toString();
 const response=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email:'hr.e2e@example.org',password}});expect(response.ok()).toBe(true);
 await page.goto('/');await page.getByRole('button',{name:'User directory',exact:true}).click();await page.getByRole('button',{name:'Import users from Excel',exact:true}).click();
 const python=process.env.MI_PYTHON ?? resolve('../backend',process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
 const buffer=execFileSync(python,['-c',`from io import BytesIO; from app.modules.imports.service import template; from openpyxl import load_workbook; import sys; b=load_workbook(BytesIO(template())); values=['BULK-${suffix}','Bulk Import Employee','bulk.${suffix}@example.org','Engineering','Engineer','India','EMPLOYEE',False,'']; [b['Users'].cell(2,i+1,v) for i,v in enumerate(values)]; s=BytesIO();b.save(s);sys.stdout.buffer.write(s.getvalue())`],{cwd:resolve('../backend')});
 await page.getByLabel('Upload completed Excel workbook (.xlsx, maximum 5 MB)').setInputFiles({name:'users.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer});
 await expect(page.getByText('Bulk Import Employee',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Confirm and create 1 users',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Private one-time setup links',exact:true})).toBeVisible();const url=await page.getByRole('textbox',{name:/Private setup link/}).inputValue();await page.goto(url);
 await page.getByLabel('New password',{exact:true}).fill(password+'-import');await page.getByLabel('Confirm new password',{exact:true}).fill(password+'-import');await page.getByRole('button',{name:'Save new password',exact:true}).click();
 await expect(page.getByText('Password reset complete. Sign in with your new password.',{exact:true})).toBeVisible();
});
