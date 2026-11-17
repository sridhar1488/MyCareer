import type { components } from '../../api/schema';
import { SubmissionReview } from '../appraisals/SubmissionReview';

type Review = components['schemas']['ReviewResponse'];
type Evaluation = components['schemas']['EvaluationInput'];
type Item = components['schemas']['ItemInput'];

function itemKey(item: Item) {
  return JSON.stringify([item.description, item.employee_narrative]);
}

export function restoreUnchangedRatings(review: Review, evaluation: Evaluation): Evaluation | null {
  const previous = review.previous_employee_responses;
  const draft = review.previous_manager_draft;
  if (!previous || !draft) return null;
  let restored = false;
  const result = {...evaluation};
  for (const section of ['goals', 'contributions'] as const) {
    const earlier = previous[section].map(itemKey);
    const current = review.employee_responses[section].map(itemKey);
    result[section] = evaluation[section].map((rating, index) => {
      const key = current[index];
      if (rating.rating != null || rating.comment?.trim() || current.indexOf(key) !== current.lastIndexOf(key)) return rating;
      const priorIndex = earlier.indexOf(key);
      if (priorIndex < 0 || priorIndex !== earlier.lastIndexOf(key)) return rating;
      const oldRating = draft[section][priorIndex];
      if (oldRating?.rating == null && !oldRating?.comment?.trim()) return rating;
      restored = true;
      return oldRating;
    });
  }
  return restored ? result : null;
}

export function RevisionComparison({ review }: { review: Review }) {
  const before = review.previous_employee_responses;
  if (!before || review.previous_submitted_revision == null) return null;
  const current = review.employee_responses;
  const changes = ([
    ['goals', 'Goals'],
    ['contributions', 'Organizational contributions'],
    ['development', 'Development and other responses'],
  ] as const).filter(([key]) => JSON.stringify(before[key]) !== JSON.stringify(current[key]));
  return <details className="panel">
    <summary>Compare submitted revisions {review.previous_submitted_revision} and {review.submitted_revision}</summary>
    <p>{changes.length ? `Response sections changed: ${changes.map(([, label]) => label).join(', ')}.` : 'No written responses changed.'}</p>
    <SubmissionReview data={{...review.appraisal, ...before}} readOnly title={`Revision ${review.previous_submitted_revision}`} />
    <SubmissionReview data={{...review.appraisal, ...current}} readOnly title={`Revision ${review.submitted_revision}`} />
  </details>;
}
