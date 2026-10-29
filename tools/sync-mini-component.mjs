// uni-app's Weixin compiler requires SFCs under each app's src directory.
// Keep one authored template and generate the two app-local build inputs.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const target=process.argv[2];
if(!['customer-mini','merchant-mini'].includes(target))throw new Error('Expected customer-mini or merchant-mini');
const source=readFileSync(resolve(root,'apps/shared/ImageSearchPanel.vue'),'utf8')
  .replace("from './catalog'","from '../../../shared/catalog'")
  .replace("from './image-search'","from '../../../shared/image-search'");
const folder=resolve(root,'apps',target,'src/components');
mkdirSync(folder,{recursive:true});
writeFileSync(resolve(folder,'ImageSearchPanel.vue'),'<!-- Generated from apps/shared/ImageSearchPanel.vue; edit that source. -->\n'+source,'utf8');
