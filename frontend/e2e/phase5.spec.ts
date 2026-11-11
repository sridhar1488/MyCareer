import {test,expect} from '@playwright/test';

const password = process.env.MI_E2E_PASSWORD!;
test('assigned manager saves review, returns with reason and reviews a fresh resubmission',async({page}) => {
  test.setTimeout(90000);
  const suffix = Date.now().toString(); const email = `review.${suffix}@example.org`; const employeeId = `REVIEW-${suffix}`;
  const managerEmail = `review.manager.${suffix}@example.org`;
  const managerPassword = `${password}-mgr`;
  async function apiLogin(address:string,secret=password) {
    const response = await page.request.post('/api/v1/auth/login',{headers:{Origin:'http://127.0.0.1:5173'},data:{email:address,password:secret}});
    expect(response.ok()).toBe(true);return (await response.json()).csrf_token as string;
  }
  let token = await apiLogin('admin.e2e@example.org');
  const adminHeaders = {'X-CSRF-Token':token,'Origin':'http://127.0.0.1:5173'};
  const managerResponse = await page.request.post('/api/v1/admin/users',{headers:adminHeaders,data:{full_name:`Review Manager ${suffix}`,email:managerEmail,employee_id:`REVIEW-MGR-${suffix}`,department:'Engineering',designation:'Manager',country:'India',role:'MANAGER',temporary_password:password}});
  expect(managerResponse.status()).toBe(201);
  const manager = await managerResponse.json();
  const employeeResponse = await page.request.post('/api/v1/admin/users',{headers:adminHeaders,data:{full_name:`Review Employee ${suffix}`,email,employee_id:employeeId,department:'Engineering',designation:'Engineer',country:'India',role:'EMPLOYEE',manager_id:manager.id,temporary_password:password}});
  expect(employeeResponse.status()).toBe(201);const employee = await employeeResponse.json();
  const cycleResponse = await page.request.post('/api/v1/cycles',{headers:adminHeaders,data:{title:`Manager review ${suffix}`,period_start:'2026-01-01',period_end:'2026-12-31',submission_deadline:new Date(Date.now()+7*86400000).toISOString(),min_goals:1,allow_late_submission:false,participant_ids:[employee.id]}});
  const cycle = await cycleResponse.json();
  expect((await page.request.post(`/api/v1/cycles/${cycle.id}/activate`,{headers:adminHeaders,data:{expected_version:1}})).ok()).toBe(true);
  token = await apiLogin(email);
  const changed = await page.request.post('/api/v1/auth/change-password',{headers:{...adminHeaders,'X-CSRF-Token':token},data:{current_password:password,new_password:password+'-own'}});
  expect(changed.ok()).toBe(true);token = (await changed.json()).csrf_token;
  const ownHeaders = {...adminHeaders,'X-CSRF-Token':token};
  const a = (await (await page.request.get('/api/v1/me/appraisals')).json()).items[0];
  const body = {expected_version:1,goals:[{description:'Delivered an assigned project',employee_narrative:'Completed the agreed milestones'}],contributions:[{description:'Mentoring',employee_narrative:'Supported a new colleague'}],development:{
    business_achievements:'Completed the project',development_achievements:'NA',six_month_growth:'NA',
    development_needs:'NA',development_plan:'NA',support_requested:'NA',
  }};
  expect((await page.request.put(`/api/v1/appraisals/${a.id}/self-assessment`,{headers:ownHeaders,data:body})).ok()).toBe(true);
  expect((await page.request.post(`/api/v1/appraisals/${a.id}/submit`,{headers:ownHeaders,data:{expected_version:2}})).ok()).toBe(true);
  token = await apiLogin(managerEmail);
  const managerCredential = await page.request.post('/api/v1/auth/change-password',{
    headers:{...adminHeaders,'X-CSRF-Token':token},data:{current_password:password,new_password:managerPassword},
  });
  expect(managerCredential.ok()).toBe(true);
  await page.goto('/');
  await page.getByRole('button',{name:'Dashboard',exact:true}).click();
  const workflow = page.getByRole('region',{name:'Team appraisal workflow by stage',exact:true});
  await expect(workflow.getByLabel('Workflow scope')).toHaveCount(0);
  await expect(workflow.locator('[data-stage="SUBMITTED"] strong')).toHaveText('1');
  await expect(page.getByRole('region',{name:'Appraisal workflow by stage',exact:true})).toHaveCount(0);
  for (const [label, status, filter] of [
    ['Assigned appraisals', '', ''],
    ['Reviews in progress', 'UNDER_REVIEW', 'state=UNDER_REVIEW'],
    ['Ready for release', 'READY_FOR_RELEASE', 'state=HR_APPROVED&release_ready=true'],
    ['Ready for review', 'SUBMITTED', 'state=SUBMITTED'],
  ]) {
    const card = page.getByRole('link',{name:new RegExp(label)});
    await expect(card).toHaveAttribute('href', status ? new RegExp(`view=team&status=${status}`) : /view=team$/);
    const response = page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname === '/api/v1/manager/appraisals' && url.searchParams.get('page') === '1';
    });
    await expect(card.locator('.dashboard-count')).toHaveText(/^\d/);
    const count = await card.locator('.dashboard-count').textContent();
    if (status === 'SUBMITTED') {
      await page.getByRole('link',{name:/Assigned appraisals/}).focus();
      await page.keyboard.press('Tab');
      await expect(card).toBeFocused();
      await expect(card).toHaveCSS('outline-style', 'solid');
      await page.keyboard.press('Enter');
    } else await card.click();
    const list = await response;
    const actualParams = new URL(list.url()).searchParams;
    expect([...actualParams].filter(([name]) => name !== 'q' && name !== 'page'))
      .toEqual([...new URLSearchParams(filter)]);
    const {total} = await list.json();
    expect(count).toBe(total.toLocaleString());
    await expect(page.getByLabel('Workflow status')).toHaveValue(status);
    if (total === 0) await expect(page.getByText('No assigned appraisals match these filters.')).toBeVisible();
    if (status !== 'SUBMITTED') await page.getByRole('button',{name:'Dashboard',exact:true}).click();
  }
  await page.getByLabel('Find an employee').fill(employeeId);
  await page.getByRole('button',{name:/Open review/}).click();
  await page.getByRole('button',{name:'Begin review',exact:true}).click();
  await expect(page.getByText('Review started.',{exact:true})).toBeVisible();
  await page.getByLabel('Rating',{exact:true}).first().selectOption('4');
  const firstComment = page.getByLabel('Supporting evaluation comment',{exact:true}).first();
  await firstComment.fill('Good progress; clarify the impact metric.');
  await page.getByRole('button',{name:'Back to top',exact:true}).click();
  const reviewStart = page.getByRole('button',{name:'Back to team appraisals',exact:true});
  await expect(reviewStart).toBeInViewport();
  await expect(reviewStart).toBeFocused();
  await expect(firstComment).toHaveValue('Good progress; clarify the impact metric.');
  await page.getByRole('button',{name:'Save manager draft',exact:true}).click();
  await expect(page.getByText('Manager review draft saved.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Return for revision',exact:true}).click();
  await expect(page.getByRole('button',{name:'Confirm return',exact:true})).toBeDisabled();
  await page.getByLabel('Reason for revision').fill('Clarify the impact metric.');
  await page.getByRole('button',{name:'Confirm return',exact:true}).click();
  await expect(page.getByText('Appraisal returned. The employee can revise their responses.',{exact:true})).toBeVisible();
  token = await apiLogin(email,password+'-own');
  const current = await (await page.request.get(`/api/v1/appraisals/${a.id}`)).json();
  expect(current.editable).toBe(true);expect(current.evaluation).toBeUndefined();
  const saved = await (await page.request.put(`/api/v1/appraisals/${a.id}/self-assessment`,{headers:{...ownHeaders,'X-CSRF-Token':token},data:{...body,expected_version:current.version,goals:[...body.goals,{description:'Additional goal',employee_narrative:'Additional result'}]}})).json();
  expect((await page.request.post(`/api/v1/appraisals/${a.id}/submit`,{headers:{...ownHeaders,'X-CSRF-Token':token},data:{expected_version:saved.version}})).ok()).toBe(true);
  await apiLogin(managerEmail,managerPassword);await page.reload();
  await page.getByRole('button',{name:'Team appraisals',exact:true}).click();await page.getByLabel('Find an employee').fill(employeeId);await page.getByRole('button',{name:/Open review/}).click();
  await expect(page.getByLabel('Rating',{exact:true}).first()).toHaveValue('');
  await expect(page.getByText('2. Additional goal',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'View manager review history',exact:true}).click();
  await page.getByText('Preserved manager draft',{exact:true}).click();
  await expect(page.getByText('Goal 1: 4 · Good progress; clarify the impact metric.',{exact:true})).toBeVisible();
  const ratings = page.getByLabel('Rating',{exact:true});
  for(let i=0;i<await ratings.count();i++) await ratings.nth(i).selectOption('4');
  const comments = page.getByLabel('Supporting evaluation comment',{exact:true});
  for(let i=0;i<await comments.count();i++) await comments.nth(i).fill('Demonstrated effective results with supporting examples.');
  await page.getByLabel('Leadership is not applicable',{exact:true}).check();
  await page.getByLabel('Leadership applicability reason',{exact:true}).fill('This role has no leadership responsibilities.');
  await page.getByLabel('What the employee did particularly well',{exact:true}).fill('Delivered the agreed work and supported colleagues.');
  await page.getByLabel('How the employee could be more effective',{exact:true}).fill('Build stronger planning and communication habits.');
  await page.getByRole('button',{name:'Save manager draft',exact:true}).click();
  await expect(page.getByText('Manager review draft saved.',{exact:true})).toBeVisible();
  await expect(page.getByText('Overall score 4.0',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Submit to HR for approval',exact:true}).click();
  await page.getByRole('button',{name:'Confirm submission to HR',exact:true}).click();
  await expect(page.getByText('Evaluation submitted to HR for calibration and approval.',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Save manager draft',exact:true})).toHaveCount(0);
  await apiLogin(email,password+'-own');
  expect((await page.request.get(`/api/v1/appraisals/${a.id}/released-result`)).status()).toBe(404);
  expect((await (await page.request.get(`/api/v1/appraisals/${a.id}`)).json()).evaluation).toBeUndefined();
  token = await apiLogin('admin.e2e@example.org');
  const hrHeaders = {'X-CSRF-Token':token,'Origin':'http://127.0.0.1:5173'};
  const calibration = await (await page.request.get(`/api/v1/hr/calibrations/${a.id}`)).json();
  const approval = await page.request.post(`/api/v1/hr/calibrations/${a.id}/approve`,{headers:hrHeaders,data:{expected_version:calibration.version,submitted_revision:calibration.submitted_revision}});
  expect(approval.ok()).toBe(true);
  await apiLogin(managerEmail,managerPassword);await page.reload();
  await page.getByRole('button',{name:'Team appraisals',exact:true}).click();await page.getByLabel('Find an employee').fill(employeeId);await page.getByRole('button',{name:/Open review/}).click();
  await page.getByRole('button',{name:'Release to employee',exact:true}).click();
  await expect(page.getByRole('button',{name:'Confirm meeting and release',exact:true})).toBeDisabled();
  await page.getByLabel('I confirm I discussed this HR-approved evaluation with the employee',{exact:true}).check();
  await page.getByRole('button',{name:'Confirm meeting and release',exact:true}).click();
  await expect(page.getByText('Evaluation released to the employee.',{exact:true})).toBeVisible();
  await apiLogin(email,password+'-own');await page.reload();
  await page.getByRole('button',{name:'View appraisal',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Your HR approved evaluation',exact:true})).toBeVisible();
  await expect(page.getByText('Overall score 4.0',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'I acknowledge receipt',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'Receipt acknowledged on'})).toBeVisible();
  await expect(page.getByRole('button',{name:'I acknowledge receipt',exact:true})).toHaveCount(0);
  await page.locator('.score-summary').scrollIntoViewIfNeeded();
  await page.screenshot({path:'../.local/phase5-released-evaluation.png'});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
