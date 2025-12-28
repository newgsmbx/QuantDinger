<template>
  <div class="main">
    <div class="auth-intro">
      <div class="desc">AI driven quantitative insights for global markets</div>
    </div>

    <div class="auth-card">
      <a-form
        id="formLogin"
        class="user-layout-login"
        ref="formLogin"
        :form="form"
        @submit="handleSubmit"
      >
        <a-alert v-if="isLoginError" type="error" showIcon style="margin-bottom: 24px;" :message="loginErrorMessage || 'Login failed'" />
        <a-alert type="info" showIcon style="margin-bottom: 16px;" message="Default account/password: quantdinger / 123456 (configurable via backend env)" />

        <a-form-item>
          <a-input
            size="large"
            type="text"
            placeholder="Username"
            v-decorator="[
              'username',
              {rules: [{ required: true, message: 'Please enter username' }], validateTrigger: 'blur'}
            ]"
          >
            <a-icon slot="prefix" type="user" :style="{ color: 'rgba(0,0,0,.25)' }"/>
          </a-input>
        </a-form-item>

        <a-form-item>
          <a-input-password
            size="large"
            placeholder="Password"
            v-decorator="[
              'password',
              {rules: [{ required: true, message: 'Please enter password' }], validateTrigger: 'blur'}
            ]"
          >
            <a-icon slot="prefix" type="lock" :style="{ color: 'rgba(0,0,0,.25)' }"/>
          </a-input-password>
        </a-form-item>

        <a-form-item style="margin-top:24px">
          <a-button
            size="large"
            type="primary"
            htmlType="submit"
            class="login-button"
            :loading="state.loginBtn"
            :disabled="state.loginBtn"
            block
          >Login</a-button>
        </a-form-item>
      </a-form>

      <div class="legal-wrap">
        <div class="legal-header">
          <div class="legal-title">{{ $t('user.login.legal.title') }}</div>
          <a class="legal-toggle" @click="showLegal = !showLegal">
            {{ showLegal ? $t('user.login.legal.collapse') : $t('user.login.legal.view') }}
          </a>
        </div>
        <div v-show="showLegal" class="legal-content">
          {{ $t('user.login.legal.content') }}
        </div>
        <div class="legal-agree">
          <a-checkbox v-model="legalAgreed">
            {{ $t('user.login.legal.agree') }}
          </a-checkbox>
          <div v-if="legalError" class="legal-error">{{ $t('user.login.legal.required') }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapActions } from 'vuex'
import { timeFix } from '@/utils/util'

export default {
  name: 'Login',
  data () {
    return {
      isLoginError: false,
      loginErrorMessage: '',
      showLegal: false,
      legalAgreed: true,
      legalError: false,
      form: this.$form.createForm(this),
      state: {
        time: 60,
        loginBtn: false
      }
    }
  },
  methods: {
    ...mapActions(['Login', 'Logout']),
    handleSubmit (e) {
      e.preventDefault()
      this.legalError = false
      if (!this.legalAgreed) {
        this.legalError = true
        return
      }
      const {
        form: { validateFields },
        state,
        Login
      } = this

      state.loginBtn = true

      validateFields(['username', 'password'], { force: true }, (err, values) => {
        if (!err) {
          const loginParams = { ...values }

          Login(loginParams)
            .then((res) => {
              this.loginSuccess(res)
            })
            .catch(err => {
              this.requestFailed(err)
            })
            .finally(() => {
              state.loginBtn = false
            })
        } else {
          setTimeout(() => {
            state.loginBtn = false
          }, 600)
        }
      })
    },
    loginSuccess (res) {
      this.$router.push({ path: '/' })
      this.isLoginError = false
      this.$notification.success({
        message: 'Welcome',
        description: `${timeFix()}, welcome back.`
      })
    },
    requestFailed (err) {
      this.isLoginError = true
      this.loginErrorMessage = ((err.response || {}).data || {}).msg || err.message || 'Incorrect username or password'
    }
  }
}
</script>

<style lang="less" scoped>
.main {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 40px 0;

  .auth-intro {
    text-align: center;
    margin-bottom: 40px;

    .brand {
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 32px;
      font-weight: 600;
      color: #1890ff;

      .brand-badge {
        background: #1890ff;
        color: #fff;
        padding: 2px 8px;
        border-radius: 4px;
        margin-right: 8px;
        font-size: 24px;
      }

      .brand-sub {
        color: rgba(0, 0, 0, 0.85);
      }
    }

    .desc {
      margin-top: 12px;
      color: rgba(0, 0, 0, 0.45);
      font-size: 14px;
    }
  }

  .auth-card {
    min-width: 360px;
    width: 380px;
    background: #fff;
    padding: 32px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  }

  .user-layout-login {
    button.login-button {
      padding: 0 15px;
      font-size: 16px;
      height: 40px;
      width: 100%;
    }
  }

  .legal-wrap {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px dashed #f0f0f0;

    .legal-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      line-height: 20px;
    }
    .legal-title {
      font-size: 13px;
      font-weight: 600;
      color: rgba(0, 0, 0, 0.75);
    }
    .legal-toggle {
      font-size: 12px;
      color: #1890ff;
    }
    .legal-content {
      margin-top: 8px;
      font-size: 12px;
      color: rgba(0, 0, 0, 0.45);
      line-height: 1.7;
      white-space: pre-wrap;
    }

    .legal-agree {
      margin-top: 10px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .legal-error {
      color: #ff4d4f;
      font-size: 12px;
      line-height: 1.4;
    }
  }
}
</style>
