<template>
    <div class="consent-form p-4 bg-light rounded">
      <h1 class="text-center mb-4">Consent Form</h1>

      <div class="consent-content mb-4">
        <h2 class="h5 mb-3">Study Information and Terms</h2>

        <div class="terms-section">
          <h3 class="mb-4">Consent Form for Participation in Speech Evaluation Study</h3>

          <h4>Purpose of the Study</h4>
          <p>
              You are invited to participate in a research study aimed at improving speech synthesis technology. Your participation involves listening to audio recordings and identifying whether they are human-spoken or machine-generated. This study will contribute to advancements in academic, research, and commercial applications.
          </p>

          <hr>

          <h4>Terms and Conditions of Participation</h4>

          <h5>Voluntary Participation</h5>
          <p>
              Participation in this study is entirely voluntary. You may withdraw at any time before completing the study without any penalty. Once your data is submitted, it cannot be withdrawn due to anonymization.
          </p>

          <h5>Data Collection</h5>
          <ul>
              <li>You will provide judgments on audio recordings during the study.</li>
              <li>Data collected will include your responses and metadata, such as timestamps and activity tracking during participation.</li>
          </ul>

          <h5>Scope of Data Usage</h5>
          <p>
              By agreeing to this consent form, you grant the researcher and their collaborators (including academic, commercial, and research entities worldwide) irrevocable, unrestricted rights to use, share, distribute, modify, and license the data collected from your participation for any lawful purpose. These purposes include, but are not limited to:
          </p>
          <ul>
              <li>Academic research and publication</li>
              <li>Development of commercial and non-commercial products</li>
              <li>Public dissemination and distribution in any format</li>
              <li>Training, testing, and deployment of machine learning models</li>
          </ul>

          <h5>Confidentiality</h5>
          <p>
              Your personal identity will not be collected or linked to the data. Data will be anonymized and securely stored to prevent unauthorized access.
          </p>

          <h5>Compensation</h5>
          <p>
              You will receive compensation as outlined in the study description, provided you meet the quality assurance criteria.
          </p>

          <h5>Quality Assurance</h5>
          <p>
              Participation is subject to adherence to the study guidelines. Failure to follow instructions or inattentiveness may result in exclusion from payment eligibility.
          </p>

          <hr>

          <h4>Legal Terms</h4>

          <h5>Release of Liability</h5>
          <p>
              By participating, you release the researcher, their collaborators, and associated entities from any claims, liabilities, or damages arising from your participation in the study or the use of the data you provide.
          </p>

          <h5>Acknowledgment of Rights</h5>
          <p>
              You understand and acknowledge that you will not retain ownership or control over the data or any derivative works created from it.
          </p>

          <hr>

          <h4>Participant Declaration</h4>
          <p>
              By checking the box below, I confirm that:
          </p>
          <ul>
              <li>I have read and understood the study description and consent form.</li>
              <li>I voluntarily agree to participate in this study.</li>
              <li>I grant the researcher and their collaborators full rights to use the data collected from my participation as described above.</li>
          </ul>
        </div>
        <div class="consent-checkbox mb-4">
          <div class="form-check">
            <input
              class="form-check-input"
              type="checkbox"
              v-model="hasConsented"
              id="consentCheck"
            >
            <label class="form-check-label" for="consentCheck">
              I have read and agree to the terms of participation
            </label>
          </div>
        </div>

        <div class="text-center">
          <button
            class="btn btn-primary btn-lg"
            @click="giveConsent"
            :disabled="!hasConsented"
          >
            Continue to Test
          </button>
        </div>
      </div>
    </div>
  </template>

  <script setup>
  import { ref } from 'vue'

  const hasConsented = ref(false)
  const emit = defineEmits(['consent-given'])

  const giveConsent = () => {
    emit('consent-given')
  }
  </script>

  <style scoped>
  .consent-form {
    max-width: 800px;
    margin: 0 auto;
    box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.1);
  }

  .terms-section {
    height: 500px;
    overflow-y: auto;
    padding: 1rem;
    border: 1px solid #dee2e6;
    border-radius: 0.25rem;
    background-color: white;
    margin-bottom: 1rem;
  }

  .consent-checkbox {
    font-size: 1.1rem;
  }
  </style>
