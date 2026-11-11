import {test,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';
const password=process.env.MI_E2E_PASSWORD!;
const origin='http://127.0.0.1:5173';

test('HR publishes a form and uses the calibration grid to download, override and approve scores',async({page})=>{
 test.setTimeout(120000);
 const suffix=Date.now().toString(),email=`custom.${suffix}@example.org`,title=`Custom appraisal ${suffix}`;
 async function login(email:string,secret=password){const response=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email,password:secret}});expect(response.ok()).toBe(true);return {'X-CSRF-Token':(await response.json()).csrf_token,Origin:origin};}
 const h=await login('admin.e2e@example.org');
 await page.goto('/');await page.getByRole('button',{name:'Appraisal forms',exact:true}).click();
 const createForm = page.getByRole('button',{name:'Create form',exact:true});
 const widths = await createForm.evaluate(button => ({
  button: button.getBoundingClientRect().width,
  container: button.parentElement!.getBoundingClientRect().width,
 }));
 expect(widths.button).toBeLessThan(widths.container);
 await createForm.click();
 await page.getByLabel('Form name',{exact:true}).fill(title);
 await page.getByRole('button',{name:'Save form draft',exact:true}).click();
 await expect(page.getByRole('button',{name:'Save form draft',exact:true})).toBeDisabled();
 await expect(page.getByRole('button',{name:'Back to forms',exact:true})).toBeEnabled();
 await page.getByRole('button',{name:'Back to forms',exact:true}).click();
 const formRow = page.getByRole('table',{name:'Appraisal forms'}).getByRole('row').filter({hasText:title});
 await expect(formRow.getByText('Draft version 1',{exact:true})).toBeVisible();
 await expect(formRow.getByText('Not published',{exact:true})).toBeVisible();
 await formRow.getByRole('button',{name:`Edit form ${title}`,exact:true}).click();
 await expect(page.getByLabel('Form name',{exact:true})).toHaveValue(title);
 await expect(page.getByLabel('Goal title character limit')).toHaveValue('500');
 await expect(page.getByLabel('Goal achievement description character limit')).toHaveValue('1000');
 await page.getByLabel('Goal title character limit').fill('60');
 await page.getByLabel('Goal achievement description character limit').fill('800');
 await page.getByRole('button',{name:'Add text section',exact:true}).click();
 await page.getByLabel('Section title',{exact:true}).fill('Personal impact');
 await page.getByLabel('Question 1',{exact:true}).fill('What changed for your customers?');
 await page.getByLabel('Required before submission / finalization').check();
 await page.getByRole('button',{name:'Preview form',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Personal impact',exact:true})).toBeVisible();
 page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Publish form version',exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:'Published version available'})).toBeVisible();
 await page.getByRole('button',{name:'Back to forms',exact:true}).click();
 await expect(formRow.getByText('Published version available',{exact:true})).toBeVisible();
 const forms=await (await page.request.get('/api/v1/hr/forms/published')).json();const form=forms.find((f:{name:string})=>f.name.startsWith(title));expect(form).toBeTruthy();
 const managers=await (await page.request.get('/api/v1/admin/users?role=MANAGER&q=E2E-manager')).json();
 const created=await page.request.post('/api/v1/admin/users',{headers:h,data:{employee_id:`CUSTOM-${suffix}`,full_name:'Custom Form Employee',email,department:'Engineering',designation:'Engineer',country:'India',role:'EMPLOYEE',manager_id:managers.items[0].id,temporary_password:password}});expect(created.status()).toBe(201);const employee=await created.json();
 const cycle=await (await page.request.post('/api/v1/cycles',{headers:h,data:{title,form_version_id:form.id,period_start:'2026-01-01',period_end:'2026-12-31',submission_deadline:new Date(Date.now()+86400000).toISOString(),min_goals:1,allow_late_submission:false,participant_ids:[employee.id]}})).json();
 expect((await page.request.post(`/api/v1/cycles/${cycle.id}/activate`,{headers:h,data:{expected_version:1}})).ok()).toBe(true);
 const eh=await login(email);expect((await page.request.post('/api/v1/auth/change-password',{headers:eh,data:{current_password:password,new_password:password+'-custom'}})).ok()).toBe(true);
 await page.reload();await page.getByRole('button',{name:'Open self-assessment',exact:true}).click();
 await expect(page.getByLabel('Responsibility / goal description',{exact:true})).toHaveAttribute('maxlength','60');
 await expect(page.getByLabel('Achievements and self-assessment',{exact:true})).toHaveAttribute('maxlength','800');
 await page.getByLabel('Responsibility / goal description',{exact:true}).fill('Customer service');await page.getByLabel('Achievements and self-assessment',{exact:true}).fill('Improved response times');
 const customAnswer=page.getByLabel('What changed for your customers? (required)',{exact:true});
 await expect(customAnswer).toHaveAccessibleDescription('1000 of 1000 characters remaining');
 await customAnswer.fill('Customers received faster support.');
 for (const field of await page.locator('textarea[id^="development-"]').all()) await field.fill('NA');
 await page.getByRole('button',{name:'Save and review submission',exact:true}).click();await expect(page.getByText('Customers received faster support.',{exact:true})).toBeVisible();
 page.once('dialog',dialog=>dialog.accept());
 await page.getByRole('button',{name:'Submit to reporting manager',exact:true}).click();
 await expect(page.getByText('Your appraisal has been submitted to your reporting manager.',{exact:true})).toBeVisible();
 await login('manager.e2e@example.org');await page.reload();await page.getByRole('button',{name:'Team appraisals',exact:true}).click();await page.getByLabel('Find an employee').fill(`CUSTOM-${suffix}`);await page.getByRole('button',{name:/Open review/}).click();
 await expect(page.getByText('Customers received faster support.',{exact:true})).toBeVisible();
 const ratings=page.getByLabel('Rating',{exact:true});for(let i=0;i<await ratings.count();i++)await ratings.nth(i).selectOption('4');
 const comments=page.getByLabel('Supporting evaluation comment',{exact:true});
 await expect(comments.first()).toHaveAccessibleDescription('1000 of 1000 characters remaining');
 for(let i=0;i<await comments.count();i++)await comments.nth(i).fill('Consistent delivery with evidence.');
 await page.getByLabel('What the employee did particularly well',{exact:true}).fill('Delivered customer improvements.');await page.getByLabel('How the employee could be more effective',{exact:true}).fill('Continue developing communication.');await page.getByRole('button',{name:'Save manager draft',exact:true}).click();await expect(page.getByText('Manager review draft saved.',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Submit to HR for approval',exact:true}).click();await page.getByRole('button',{name:'Confirm submission to HR',exact:true}).click();await expect(page.getByText('Evaluation submitted to HR for calibration and approval.',{exact:true})).toBeVisible();
 await login('hr.e2e@example.org');
 await page.reload();
 await page.getByRole('button',{name:'Dashboard',exact:true}).click();
 const workflow = page.getByRole('region',{name:'Appraisal workflow by stage',exact:true});
 await expect(workflow.getByLabel('Workflow scope')).toHaveCount(0);
 const monitor = await page.request.get('/api/v1/hr/monitor?page_size=1');
 expect(monitor.ok()).toBe(true);
 const {total: workflowTotal, status_counts: stageCounts} = await monitor.json();
 expect(stageCounts.HR_REVIEW).toBeGreaterThan(0);
 await expect(workflow.getByText(`${workflowTotal.toLocaleString()} total`,{exact:true})).toBeVisible();
 for (const [stage, count] of Object.entries(stageCounts as Record<string, number>)) {
  const stageRow = workflow.locator(`[data-stage="${stage}"]`);
  if (stage === 'FINALIZED' && count === 0) await expect(stageRow).toHaveCount(0);
  else await expect(stageRow.locator('strong')).toHaveText(count.toLocaleString());
 }
 for (const [label, path] of [
  ['Organization appraisals', '/api/v1/hr/monitor'],
  ['Approved evaluations', '/api/v1/hr/evaluations'],
  ['Waiting for HR approval', '/api/v1/hr/calibrations'],
 ]) {
  const card=page.getByRole('link',{name:new RegExp(label)});
  await expect(card.locator('.dashboard-count')).toHaveText(/^\d/);
  const count=await card.locator('.dashboard-count').textContent();
  const response=page.waitForResponse(response=>{
   const url=new URL(response.url());
   return url.pathname===path && url.searchParams.get('page_size')!=='1';
  });
  await card.click();
  const {total}=await (await response).json();
  expect(count).toBe(total.toLocaleString());
  if (path.endsWith('evaluations') && total===0) await expect(page.getByText('No approved evaluations match these filters.')).toBeVisible();
  if (!path.endsWith('calibrations')) await page.goBack();
 }
 await page.getByLabel('Search employee or manager').fill(`CUSTOM-${suffix}`);
 await page.getByRole('button',{name:'Search',exact:true}).click();
 const row = page.getByRole('row').filter({hasText:`CUSTOM-${suffix}`});
 await expect(row).toContainText(form.name);
 await expect(row.getByRole('cell',{name:'3.6',exact:true})).toBeVisible();
 await expect(row.getByRole('cell').filter({has:page.getByRole('button',{name:'Override score',exact:true})})).toContainText('3.6');
 await expect(page.getByRole('columnheader',{name:'Manager comments',exact:true})).toHaveCount(0);
 await expect(row.getByText('View narrative',{exact:true})).toHaveCount(0);
 await row.getByRole('button',{name:'Review and calibrate',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Manager narrative',exact:true})).toBeVisible();
 await expect(page.getByText('Strengths: Delivered customer improvements.',{exact:true}).first()).toBeVisible();
 await page.getByRole('button',{name:'Back to calibration queue',exact:true}).click();
 await row.getByRole('button',{name:'Override score',exact:true}).click();
 await row.getByLabel('Overall score').fill('4.2');
 await expect(row.getByRole('button',{name:'Save score',exact:true})).toBeDisabled();
 const overrideReason=row.getByLabel('Reason',{exact:true});
 await expect(overrideReason).toHaveAccessibleDescription('1000 of 1000 characters remaining');
 await overrideReason.fill('N');
 await expect(overrideReason).toHaveAttribute('aria-invalid','true');
 await expect(row.getByRole('button',{name:'Save score',exact:true})).toBeDisabled();
 await overrideReason.fill('Calibration discussion confirmed a higher overall score.');
 await row.getByRole('button',{name:'Save score',exact:true}).click();
 await expect(row).toContainText('HR override · Calculated 3.6');
 const gridDownload = page.waitForEvent('download');
 await page.getByRole('button',{name:'Download calibration grid · Excel',exact:true}).click();
 const grid = await gridDownload;
 expect(grid.suggestedFilename()).toBe('hr-calibration-queue.xlsx');
 expect(await grid.failure()).toBeNull();
 page.once('dialog',dialog=>dialog.accept());
 await row.getByRole('button',{name:'Approve',exact:true}).click();
 await expect(row).toHaveCount(0);
 await login('manager.e2e@example.org');await page.reload();await page.getByRole('button',{name:'Dashboard',exact:true}).click();
 await expect(workflow).toHaveCount(0);
 const releaseCard = page.getByRole('link',{name:/Ready for release/});
 await expect(releaseCard.locator('.dashboard-count')).toHaveText('1');
 await releaseCard.click();
 await expect(page.getByLabel('Workflow status')).toHaveValue('READY_FOR_RELEASE');
 await page.getByLabel('Find an employee').fill(`CUSTOM-${suffix}`);await page.getByRole('button',{name:/Open review/}).click();await page.getByRole('button',{name:'Release to employee',exact:true}).click();await page.getByLabel('I confirm I discussed this HR-approved evaluation with the employee',{exact:true}).check();await page.getByRole('button',{name:'Confirm meeting and release',exact:true}).click();await expect(page.getByText('Evaluation released to the employee.',{exact:true})).toBeVisible();
 await login('hr.e2e@example.org');await page.reload();await page.getByRole('button',{name:'HR monitoring',exact:true}).click();await expect(page.getByRole('heading',{name:'HR appraisal monitoring',exact:true})).toBeVisible();
 const analyticsPanel = page.locator('.hr-analytics');
 await analyticsPanel.getByRole('combobox',{name:'Cycle',exact:true}).selectOption(cycle.id,{timeout:10000});
 await expect(analyticsPanel.getByRole('heading',{name:'Employee score distribution'})).toBeVisible();
 for (const width of [1280, 900, 390]) {
  await page.setViewportSize({width,height:844});
  const excel = await analyticsPanel.getByRole('button',{name:'Download analytics · Excel',exact:true}).boundingBox();
  const pdf = await analyticsPanel.getByRole('button',{name:'Download analytics · PDF',exact:true}).boundingBox();
  expect(excel).not.toBeNull();
  expect(pdf).not.toBeNull();
  expect(Math.abs(excel!.y - pdf!.y)).toBeLessThan(1);
  expect(Math.abs(excel!.height - pdf!.height)).toBeLessThan(1);
  expect(pdf!.x + pdf!.width).toBeLessThanOrEqual(width);
  const toolbar = await analyticsPanel.locator('.analytics-actions').boundingBox();
  expect(Math.abs(pdf!.x + pdf!.width - toolbar!.x - toolbar!.width)).toBeLessThan(1);
  if (width >= 900) {
   const cycleSelect = await analyticsPanel.getByRole('combobox',{name:'Cycle',exact:true}).boundingBox();
   expect(Math.abs(cycleSelect!.y - excel!.y)).toBeLessThan(1);
   expect(Math.abs(cycleSelect!.height - excel!.height)).toBeLessThan(1);
  }
 }
 await page.setViewportSize({width:1280,height:844});
 for (const [format, label] of [['xlsx', 'Excel'], ['pdf', 'PDF']]) {
  const analyticsResponse = page.waitForResponse(response => response.url().includes(`/hr/analytics/export/${format}`));
  const analyticsDownload = page.waitForEvent('download');
  await analyticsPanel.getByRole('button',{name:`Download analytics · ${label}`,exact:true}).click();
  const file = await analyticsDownload;
  expect(file.suggestedFilename()).toBe(`hr-analytics.${format}`);
  expect(await file.failure()).toBeNull();
  const exportResponse = await analyticsResponse;
  expect(new URL(exportResponse.url()).searchParams.get('cycle_id')).toBe(cycle.id);
  expect(exportResponse.ok()).toBe(true);
 }
 await page.getByRole('button',{name:'Final evaluations',exact:true}).click();await page.getByLabel('Search employee or manager').fill(`CUSTOM-${suffix}`);await page.getByRole('button',{name:'View final evaluation',exact:true}).click();await expect(page.getByText('Customers received faster support.',{exact:true})).toBeVisible();await expect(page.getByText('Overall score 4.2',{exact:false})).toBeVisible();
 for(const format of ['Excel','PDF']){const event=page.waitForEvent('download');await page.getByRole('button',{name:`Download evaluation · ${format}`,exact:true}).click();const downloaded=await event;expect(downloaded.suggestedFilename()).toContain(format==='Excel'?'.xlsx':'.pdf');expect(await downloaded.failure()).toBeNull();}
 await page.screenshot({path:'../.local/hr-final-evaluation.png',fullPage:true});
});

test('Excel import previews users and returns a working private setup link',async({page})=>{
 test.setTimeout(90000);const suffix=Date.now().toString();
 const response=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email:'hr.e2e@example.org',password}});expect(response.ok()).toBe(true);
 await page.goto('/');await page.getByRole('button',{name:'User directory',exact:true}).click();await page.getByRole('button',{name:'Import users from Excel',exact:true}).click();
 const python=process.env.MI_PYTHON ?? resolve('../backend',process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
 const buffer=execFileSync(python,['-c',`from io import BytesIO; from app.modules.imports.service import template; from openpyxl import load_workbook; import sys; b=load_workbook(BytesIO(template())); values=['BULK-${suffix}','Bulk Import Employee','bulk.${suffix}@example.org','Bengaluru','Engineering','Engineer','','2020-01-01']; [b['Users'].cell(2,i+1,v) for i,v in enumerate(values)]; s=BytesIO();b.save(s);sys.stdout.buffer.write(s.getvalue())`],{cwd:resolve('../backend')});
 await page.getByLabel('Upload completed Excel workbook (.xlsx, maximum 5 MB)').setInputFiles({name:'users.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer});
 await expect(page.getByText('Bulk Import Employee',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Confirm and create 1 users',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Private one-time setup links',exact:true})).toBeVisible();const url=await page.getByRole('textbox',{name:/Private setup link/}).inputValue();await page.goto(url);
 await page.getByLabel('New password',{exact:true}).fill(password+'-import');await page.getByLabel('Confirm new password',{exact:true}).fill(password+'-import');await page.getByRole('button',{name:'Save new password',exact:true}).click();
 await expect(page.getByText('Password reset complete. Sign in with your new password.',{exact:true})).toBeVisible();
});

test('Super Admin can add Manager to their account without losing Super Admin access',async({page})=>{
 const response=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email:'admin.e2e@example.org',password}});expect(response.ok()).toBe(true);
 await page.goto('/');await page.getByRole('button',{name:'User directory',exact:true}).click();
 await page.getByLabel('Search users',{exact:true}).fill('admin.e2e@example.org');
 const account=page.getByRole('row').filter({hasText:'admin.e2e@example.org'});
 await account.getByRole('button',{name:'Change role for Test Admin',exact:true}).click();
 await page.getByLabel('Role',{exact:true}).selectOption('MANAGER');
 const additionalAccess=page.getByLabel('Additional HR / Super Admin access',{exact:true});
 await expect(additionalAccess).toBeChecked();await expect(additionalAccess).toBeDisabled();
 const changed=page.waitForResponse(r=>r.url().includes('/role')&&r.request().method()==='PUT');
 await page.getByRole('button',{name:'Confirm change',exact:true}).click();
 expect((await changed).ok()).toBe(true);
 const hr=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email:'hr.e2e@example.org',password}});expect(hr.ok()).toBe(true);
 const directory=await (await page.request.get('/api/v1/admin/users?q=admin.e2e%40example.org')).json();
 expect(directory.items[0].roles).toEqual(['MANAGER','SUPER_ADMIN']);
 const admin=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email:'admin.e2e@example.org',password}});
 expect(admin.ok()).toBe(true);
 await page.goto('/?view=dashboard');
 const assigned = page.getByRole('link',{name:/Assigned appraisals/});
 await expect(assigned.locator('.dashboard-count')).toHaveText('0');
 await expect(assigned).toHaveAttribute('data-accent','neutral');
 const organization = page.getByRole('link',{name:/Organization appraisals/});
 await expect(organization.locator('.dashboard-count')).toHaveText(/^[1-9]/);
 const teamChart = page.getByRole('region',{name:'Team appraisal workflow by stage',exact:true});
 const organizationChart = page.getByRole('region',{name:'Appraisal workflow by stage',exact:true});
 const scope = page.getByLabel('Workflow scope');
 await expect(scope).toHaveValue('organization');
 await expect(teamChart).toHaveCount(0);
 await expect(organizationChart.getByText(`${await organization.locator('.dashboard-count').textContent()} total`,{exact:true})).toBeVisible();
 await scope.selectOption('team');
 await expect(teamChart).toContainText('No team appraisals have been assigned to you yet.');
 await expect(organizationChart).toHaveCount(0);
 await scope.selectOption('organization');
 await expect(teamChart).toHaveCount(0);
 await expect(organizationChart).toBeVisible();
 await expect(page.locator('.workspace-body')).toHaveCSS('background-color','rgb(255, 255, 255)');
 for (const [width, hrColumns, managerColumns] of [[1280,3,4],[900,2,2],[390,1,1]]) {
  await page.setViewportSize({width,height:844});
  for (const [selector, columns] of [['.dashboard-grid-hr',hrColumns],['.dashboard-grid-manager',managerColumns]] as const) {
   const layout = await page.locator(selector).evaluate(grid => {
    const cards = Array.from(grid.children, card => card.getBoundingClientRect());
    const row = cards.filter(card => Math.abs(card.top - cards[0].top) < 1);
    return {columns: row.length, heights: row.map(card => card.height), widths: row.map(card => card.width)};
   });
   expect(layout.columns).toBe(columns);
   expect(Math.max(...layout.heights) - Math.min(...layout.heights)).toBeLessThan(1);
   expect(Math.max(...layout.widths) - Math.min(...layout.widths)).toBeLessThan(1);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
 }
 await assigned.click();
 await expect(page.getByText('No assigned appraisals match these filters.')).toBeVisible();
});
