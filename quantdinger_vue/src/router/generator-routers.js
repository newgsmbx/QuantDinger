import { asyncRouterMap } from '@/config/router.config'

/**
 * Local-only mode: generate routes from frontend static config.
 * This removes dependency on legacy PHP `/user/nav`.
 */
export const generatorDynamicRouter = token => {
  return Promise.resolve(asyncRouterMap)
}
