import type { components } from '../../api/schema';
import type { Config } from '../forms/config';
import { isSingleCharacter } from '../../utils/appraisalTextLimits';

type Evaluation = components['schemas']['EvaluationInput'];

export function reviewFieldErrors(evaluation: Evaluation, config: Config) {
  const fields: Record<string, string> = {};
  function checkText(id: string, text: string | undefined, required: boolean, message: string) {
    if (required && !text?.trim()) fields[id] = message;
    else if (isSingleCharacter(text ?? '')) fields[id] = 'Enter at least 2 characters.';
  }
  for (const [section, prefix] of [['goals', 'goals'], ['contributions', 'contributions'], ['competencies', 'competency']] as const) {
    evaluation[section].forEach((rating, index) => {
      const id = `${prefix}-${index}`;
      if (rating.not_applicable) {
        checkText(`${id}-reason`, rating.applicability_reason, true, 'Explain why leadership is not applicable.');
      } else {
        if (rating.rating == null) fields[`${id}-rating`] = 'Select a rating from 1 to 5.';
        checkText(`${id}-comment`, rating.comment, true, 'Enter a supporting evaluation comment.');
      }
    });
  }
  checkText('strengths', evaluation.strengths, true, 'Describe what the employee did well.');
  checkText('improvements', evaluation.improvements, true, 'Describe how the employee could be more effective.');
  for (const section of config.text_sections ?? []) {
    if (section.owner !== 'MANAGER') continue;
    for (const question of section.questions) {
      checkText(`question-${question.id}`, evaluation.extra_answers?.[question.id], Boolean(question.required), 'Enter a response.');
    }
  }
  return fields;
}
